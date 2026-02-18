"""
Catalog Service - Product catalog management microservice.

Designed with rich Pydantic constraints, IDOR patterns, and
cross-field validators to exercise Logic-oriented Fuzzing (LoF).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

app = FastAPI(title="Catalog Service", version="1.0.0")

# ---------------------------------------------------------------------------
# Type aliases — Literal enums for LoF enum-violation generation
# ---------------------------------------------------------------------------

CategoryCode = Literal[
    "electronics", "clothing", "food", "books",
    "sports", "home", "beauty", "toys"
]

ProductStatus = Literal["draft", "active", "archived", "out_of_stock"]

SortOrder = Literal["price_asc", "price_desc", "rating_desc", "newest", "popular"]

ContentRating = Literal["general", "teen", "mature"]

VisibilityLevel = Literal["public", "members_only", "private"]

ReviewStatus = Literal["pending", "approved", "rejected", "flagged"]

ReportFormat = Literal["csv", "json", "xlsx", "pdf"]

DiscountType = Literal["percentage", "fixed_amount", "buy_x_get_y", "bundle"]

# ---------------------------------------------------------------------------
# Auth dependency (IDOR signal: current_user ownership checks)
# ---------------------------------------------------------------------------


class CurrentUser(BaseModel):
    id: str
    role: Literal["user", "vendor", "moderator"]
    email: str


def get_current_user() -> CurrentUser:
    """Mock dependency — replaced by real JWT in production."""
    return CurrentUser(id="user-123", role="user", email="user@example.com")


# ---------------------------------------------------------------------------
# Request models — product management
# ---------------------------------------------------------------------------


class CreateProductRequest(BaseModel):
    name: Annotated[str, Field(min_length=3, max_length=120)]
    description: Annotated[str, Field(min_length=10, max_length=5000)]
    category: CategoryCode
    price: Annotated[float, Field(gt=0, lt=1_000_000, description="Base price in USD")]
    sale_price: Annotated[Optional[float], Field(default=None, gt=0, lt=1_000_000)]
    stock_quantity: Annotated[int, Field(ge=0, le=999_999)]
    sku: Annotated[str, Field(min_length=6, max_length=32, pattern=r"^[A-Z0-9\-]+$")]
    weight_kg: Annotated[Optional[float], Field(default=None, ge=0, le=500)]
    tags: Annotated[List[str], Field(default_factory=list, max_length=10)]
    status: ProductStatus = "draft"
    visibility: VisibilityLevel = "public"
    content_rating: ContentRating = "general"

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: List[str]) -> List[str]:
        for tag in tags:
            if len(tag) < 2 or len(tag) > 30:
                raise ValueError("Each tag must be 2-30 characters")
        return [t.lower().strip() for t in tags]

    @model_validator(mode="after")
    def validate_sale_price(self) -> CreateProductRequest:
        if self.sale_price is not None and self.sale_price >= self.price:
            raise ValueError("sale_price must be strictly less than price")
        return self


class UpdateProductRequest(BaseModel):
    name: Annotated[Optional[str], Field(default=None, min_length=3, max_length=120)]
    description: Annotated[Optional[str], Field(default=None, min_length=10, max_length=5000)]
    price: Annotated[Optional[float], Field(default=None, gt=0, lt=1_000_000)]
    sale_price: Annotated[Optional[float], Field(default=None, gt=0, lt=1_000_000)]
    stock_quantity: Annotated[Optional[int], Field(default=None, ge=0, le=999_999)]
    status: Optional[ProductStatus] = None
    visibility: Optional[VisibilityLevel] = None


class AdjustStockRequest(BaseModel):
    delta: Annotated[int, Field(ge=-10_000, le=10_000, description="Positive=add, negative=remove")]
    reason: Annotated[str, Field(min_length=5, max_length=200)]


# ---------------------------------------------------------------------------
# Request models — reviews
# ---------------------------------------------------------------------------


class CreateReviewRequest(BaseModel):
    product_id: Annotated[str, Field(min_length=36, max_length=36)]
    rating: Annotated[float, Field(ge=1.0, le=5.0)]
    title: Annotated[str, Field(min_length=5, max_length=100)]
    body: Annotated[str, Field(min_length=20, max_length=2000)]
    pros: Annotated[List[str], Field(default_factory=list, max_length=5)]
    cons: Annotated[List[str], Field(default_factory=list, max_length=5)]
    verified_purchase: bool = False

    @field_validator("rating")
    @classmethod
    def validate_rating_precision(cls, v: float) -> float:
        # Allow only 0.5 increments
        if round(v * 2) != v * 2:
            raise ValueError("Rating must be in 0.5 increments (1.0, 1.5, …, 5.0)")
        return v


class ModerateReviewRequest(BaseModel):
    review_id: Annotated[str, Field(min_length=36, max_length=36)]
    action: ReviewStatus
    moderator_note: Annotated[Optional[str], Field(default=None, max_length=500)]


# ---------------------------------------------------------------------------
# Request models — wishlist
# ---------------------------------------------------------------------------


class WishlistAddRequest(BaseModel):
    product_id: Annotated[str, Field(min_length=36, max_length=36)]
    priority: Annotated[int, Field(ge=1, le=10, description="1=lowest, 10=highest")]
    note: Annotated[Optional[str], Field(default=None, max_length=300)]


class WishlistShareRequest(BaseModel):
    user_ids: Annotated[List[str], Field(min_length=1, max_length=50)]
    message: Annotated[Optional[str], Field(default=None, max_length=500)]


# ---------------------------------------------------------------------------
# Request models — discounts / promotions
# ---------------------------------------------------------------------------


class CreateDiscountRequest(BaseModel):
    code: Annotated[str, Field(min_length=4, max_length=20, pattern=r"^[A-Z0-9]+$")]
    discount_type: DiscountType
    value: Annotated[float, Field(gt=0)]
    max_uses: Annotated[Optional[int], Field(default=None, ge=1, le=1_000_000)]
    min_order_amount: Annotated[Optional[float], Field(default=None, ge=0)]
    valid_days: Annotated[int, Field(ge=1, le=365)]

    @model_validator(mode="after")
    def validate_percentage_value(self) -> CreateDiscountRequest:
        if self.discount_type == "percentage" and self.value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        return self


class BulkPriceUpdateRequest(BaseModel):
    product_ids: Annotated[List[str], Field(min_length=1, max_length=200)]
    adjustment_type: Literal["fixed", "percentage"]
    adjustment_value: Annotated[float, Field(gt=0)]
    price_floor: Annotated[Optional[float], Field(default=None, ge=0.01)]

    @model_validator(mode="after")
    def validate_percentage_adjustment(self) -> BulkPriceUpdateRequest:
        if self.adjustment_type == "percentage" and self.adjustment_value > 100:
            raise ValueError("Percentage adjustment cannot exceed 100")
        return self


# ---------------------------------------------------------------------------
# Request models — catalog export / reports
# ---------------------------------------------------------------------------


class ExportCatalogRequest(BaseModel):
    format: ReportFormat
    category: Optional[CategoryCode] = None
    include_archived: bool = False
    max_records: Annotated[int, Field(ge=1, le=50_000)] = 10_000
    min_price: Annotated[Optional[float], Field(default=None, ge=0)]
    max_price: Annotated[Optional[float], Field(default=None, ge=0)]

    @model_validator(mode="after")
    def validate_price_range(self) -> ExportCatalogRequest:
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price must not exceed max_price")
        return self


# ---------------------------------------------------------------------------
# In-memory data stores
# ---------------------------------------------------------------------------

_products: Dict[str, dict] = {}
_reviews: Dict[str, dict] = {}
_wishlists: Dict[str, List[dict]] = {}
_discounts: Dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Products endpoints
# ---------------------------------------------------------------------------


@app.post("/api/catalog/products", status_code=201)
def create_product(
    body: CreateProductRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    product_id = str(uuid.uuid4())
    product = {
        "id": product_id,
        "vendor_id": current_user.id,
        **body.model_dump(),
        "created_at": datetime.utcnow().isoformat(),
    }
    _products[product_id] = product
    return product


@app.get("/api/catalog/products")
def list_products(
    category: Optional[CategoryCode] = None,
    status: Optional[ProductStatus] = None,
    sort: SortOrder = "newest",
    min_price: Annotated[Optional[float], Query(ge=0)] = None,
    max_price: Annotated[Optional[float], Query(ge=0)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items = list(_products.values())

    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(400, "min_price must not exceed max_price")

    if category:
        items = [p for p in items if p["category"] == category]
    if status:
        items = [p for p in items if p["status"] == status]
    if min_price is not None:
        items = [p for p in items if p["price"] >= min_price]
    if max_price is not None:
        items = [p for p in items if p["price"] <= max_price]

    start = (page - 1) * page_size
    return {"items": items[start: start + page_size], "total": len(items)}


@app.get("/api/catalog/products/{product_id}")
def get_product(product_id: str) -> dict:
    product = _products.get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@app.put("/api/catalog/products/{product_id}")
def update_product(
    product_id: str,
    body: UpdateProductRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    product = _products.get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    # IDOR: only the vendor who created the product can update it
    if product["vendor_id"] != current_user.id:
        raise HTTPException(403, "Cannot update another vendor's product")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    product.update(updates)
    return product


@app.delete("/api/catalog/products/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    product = _products.get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    # IDOR: only the vendor can delete their own product
    if product["vendor_id"] != current_user.id:
        raise HTTPException(403, "Cannot delete another vendor's product")

    del _products[product_id]


@app.patch("/api/catalog/products/{product_id}/stock")
def adjust_stock(
    product_id: str,
    body: AdjustStockRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    product = _products.get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    if product["vendor_id"] != current_user.id:
        raise HTTPException(403, "Cannot adjust stock of another vendor's product")

    new_stock = product["stock_quantity"] + body.delta
    if new_stock < 0:
        raise HTTPException(400, f"Insufficient stock. Current: {product['stock_quantity']}, delta: {body.delta}")

    product["stock_quantity"] = new_stock
    return {"product_id": product_id, "new_stock": new_stock}


# ---------------------------------------------------------------------------
# Reviews endpoints
# ---------------------------------------------------------------------------


@app.post("/api/catalog/reviews", status_code=201)
def create_review(
    body: CreateReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    product = _products.get(body.product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    review_id = str(uuid.uuid4())
    review = {
        "id": review_id,
        "author_id": current_user.id,
        **body.model_dump(),
        "status": "pending",
        "helpful_votes": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    _reviews[review_id] = review
    return review


@app.get("/api/catalog/reviews/{review_id}")
def get_review(review_id: str) -> dict:
    review = _reviews.get(review_id)
    if not review:
        raise HTTPException(404, "Review not found")
    return review


@app.put("/api/catalog/reviews/{review_id}")
def update_review(
    review_id: str,
    body: CreateReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    review = _reviews.get(review_id)
    if not review:
        raise HTTPException(404, "Review not found")

    # IDOR: only the review author can edit it
    if review["author_id"] != current_user.id:
        raise HTTPException(403, "Cannot edit another user's review")

    review.update(body.model_dump())
    return review


@app.delete("/api/catalog/reviews/{review_id}", status_code=204)
def delete_review(
    review_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    review = _reviews.get(review_id)
    if not review:
        raise HTTPException(404, "Review not found")

    if review["author_id"] != current_user.id:
        raise HTTPException(403, "Cannot delete another user's review")

    del _reviews[review_id]


@app.post("/api/catalog/reviews/moderate")
def moderate_review(
    body: ModerateReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if current_user.role not in ("moderator",):
        raise HTTPException(403, "Only moderators can moderate reviews")

    review = _reviews.get(body.review_id)
    if not review:
        raise HTTPException(404, "Review not found")

    review["status"] = body.action
    if body.moderator_note:
        review["moderator_note"] = body.moderator_note
    return review


# ---------------------------------------------------------------------------
# Wishlist endpoints
# ---------------------------------------------------------------------------


@app.get("/api/catalog/wishlists/{user_id}")
def get_wishlist(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    # IDOR: users can only see their own wishlist
    if user_id != current_user.id:
        raise HTTPException(403, "Cannot view another user's wishlist")

    return {"user_id": user_id, "items": _wishlists.get(user_id, [])}


@app.post("/api/catalog/wishlists/{user_id}/items", status_code=201)
def add_to_wishlist(
    user_id: str,
    body: WishlistAddRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    # IDOR: only the owner can add to their wishlist
    if user_id != current_user.id:
        raise HTTPException(403, "Cannot modify another user's wishlist")

    product = _products.get(body.product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    wishlist = _wishlists.setdefault(user_id, [])

    # Max 500 items per wishlist
    if len(wishlist) >= 500:
        raise HTTPException(400, "Wishlist is full (max 500 items)")

    item = {
        "product_id": body.product_id,
        "priority": body.priority,
        "note": body.note,
        "added_at": datetime.utcnow().isoformat(),
    }
    wishlist.append(item)
    return item


@app.delete("/api/catalog/wishlists/{user_id}/items/{product_id}", status_code=204)
def remove_from_wishlist(
    user_id: str,
    product_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    if user_id != current_user.id:
        raise HTTPException(403, "Cannot modify another user's wishlist")

    wishlist = _wishlists.get(user_id, [])
    original_len = len(wishlist)
    _wishlists[user_id] = [i for i in wishlist if i["product_id"] != product_id]

    if len(_wishlists[user_id]) == original_len:
        raise HTTPException(404, "Product not in wishlist")


@app.post("/api/catalog/wishlists/{user_id}/share")
def share_wishlist(
    user_id: str,
    body: WishlistShareRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(403, "Cannot share another user's wishlist")

    return {"shared_with": body.user_ids, "message": body.message}


# ---------------------------------------------------------------------------
# Discount / promotion endpoints
# ---------------------------------------------------------------------------


@app.post("/api/catalog/discounts", status_code=201)
def create_discount(
    body: CreateDiscountRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if current_user.role not in ("vendor", "moderator"):
        raise HTTPException(403, "Only vendors and moderators can create discounts")

    if body.code in _discounts:
        raise HTTPException(409, "Discount code already exists")

    discount = {
        "id": str(uuid.uuid4()),
        "created_by": current_user.id,
        **body.model_dump(),
        "uses": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    _discounts[body.code] = discount
    return discount


@app.post("/api/catalog/discounts/validate")
def validate_discount(
    code: Annotated[str, Field(min_length=4, max_length=20)],
    order_amount: Annotated[float, Field(gt=0)],
) -> dict:
    discount = _discounts.get(code)
    if not discount:
        raise HTTPException(404, "Discount code not found")

    if discount.get("min_order_amount") and order_amount < discount["min_order_amount"]:
        raise HTTPException(400, f"Minimum order amount is {discount['min_order_amount']}")

    if discount.get("max_uses") and discount["uses"] >= discount["max_uses"]:
        raise HTTPException(400, "Discount code has reached its usage limit")

    return {"valid": True, "discount": discount}


@app.post("/api/catalog/products/bulk-price-update")
def bulk_price_update(
    body: BulkPriceUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if current_user.role not in ("vendor", "moderator"):
        raise HTTPException(403, "Insufficient permissions for bulk price update")

    updated = []
    skipped = []

    for product_id in body.product_ids:
        product = _products.get(product_id)
        if not product:
            skipped.append({"id": product_id, "reason": "not_found"})
            continue

        # IDOR: vendors can only update their own products
        if current_user.role == "vendor" and product["vendor_id"] != current_user.id:
            skipped.append({"id": product_id, "reason": "not_owner"})
            continue

        old_price = product["price"]
        if body.adjustment_type == "percentage":
            new_price = old_price * (1 - body.adjustment_value / 100)
        else:
            new_price = old_price - body.adjustment_value

        if body.price_floor and new_price < body.price_floor:
            new_price = body.price_floor

        if new_price <= 0:
            skipped.append({"id": product_id, "reason": "price_would_be_zero_or_negative"})
            continue

        product["price"] = round(new_price, 2)
        updated.append({"id": product_id, "old_price": old_price, "new_price": product["price"]})

    return {"updated": updated, "skipped": skipped}


# ---------------------------------------------------------------------------
# Export endpoint
# ---------------------------------------------------------------------------


@app.post("/api/catalog/export")
def export_catalog(
    body: ExportCatalogRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    items = list(_products.values())

    if body.category:
        items = [p for p in items if p["category"] == body.category]
    if not body.include_archived:
        items = [p for p in items if p.get("status") != "archived"]
    if body.min_price is not None:
        items = [p for p in items if p["price"] >= body.min_price]
    if body.max_price is not None:
        items = [p for p in items if p["price"] <= body.max_price]

    items = items[: body.max_records]

    return {
        "format": body.format,
        "record_count": len(items),
        "download_url": f"/api/catalog/export/download/{uuid.uuid4()}.{body.format}",
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {
        "status": "healthy",
        "service": "catalog-service",
        "products": len(_products),
        "reviews": len(_reviews),
    }

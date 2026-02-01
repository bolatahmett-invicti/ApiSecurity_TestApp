using Microsoft.AspNetCore.Mvc;

namespace InventoryService.Controllers;

[ApiController]
[Route("api")]
public class InventoryController : ControllerBase
{
    private readonly InventoryStore _store;

    public InventoryController(InventoryStore store)
    {
        _store = store;
    }

    // GET /health
    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new
        {
            status = "healthy",
            service = "inventory-service",
            timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
        });
    }

    // GET /api/inventory
    [HttpGet("inventory")]
    public IActionResult GetAll()
    {
        return Ok(_store.GetAll());
    }

    // GET /api/inventory/{id}
    [HttpGet("inventory/{id}")]
    public IActionResult GetById(string id)
    {
        var item = _store.GetById(id);
        if (item == null)
            return NotFound(new { error = "Product not found" });

        return Ok(item);
    }

    // POST /api/inventory
    [HttpPost("inventory")]
    public IActionResult Create([FromBody] InventoryItem item)
    {
        if (string.IsNullOrEmpty(item.Id))
            item.Id = $"prod-{Random.Shared.Next(1000, 9999)}";

        if (string.IsNullOrEmpty(item.Location))
            item.Location = "Warehouse A";

        _store.Add(item);
        return CreatedAtAction(nameof(GetById), new { id = item.Id }, item);
    }

    // PUT /api/inventory/{id}
    [HttpPut("inventory/{id}")]
    public IActionResult Update(string id, [FromBody] UpdateInventoryRequest request)
    {
        var item = _store.GetById(id);
        if (item == null)
            return NotFound(new { error = "Product not found" });

        if (request.Quantity.HasValue)
            item.Quantity = request.Quantity.Value;

        if (!string.IsNullOrEmpty(request.Location))
            item.Location = request.Location;

        _store.Update(id, item);
        return Ok(item);
    }

    // DELETE /api/inventory/{id}
    [HttpDelete("inventory/{id}")]
    public IActionResult Delete(string id)
    {
        if (!_store.Delete(id))
            return NotFound(new { error = "Product not found" });

        return Ok(new { success = true, message = "Item deleted" });
    }

    // POST /api/inventory/reserve
    [HttpPost("inventory/reserve")]
    public IActionResult Reserve([FromBody] ReserveRequest request)
    {
        var item = _store.GetById(request.ProductId);
        
        if (item == null)
            return NotFound(new { error = "Product not found" });

        if (item.Quantity >= request.Quantity)
        {
            item.Quantity -= request.Quantity;
            _store.Update(request.ProductId, item);
            
            return Ok(new ReserveResponse
            {
                Success = true,
                Reserved = request.Quantity,
                Remaining = item.Quantity
            });
        }

        return BadRequest(new ReserveResponse
        {
            Success = false,
            Error = "Insufficient inventory",
            Available = item.Quantity
        });
    }

    // GET /api/inventory/low-stock
    [HttpGet("inventory/low-stock")]
    public IActionResult GetLowStock([FromQuery] int threshold = 100)
    {
        var lowStock = _store.GetLowStock(threshold);
        return Ok(lowStock);
    }

    // GET /api/admin/inventory/location/{location}
    [HttpGet("admin/inventory/location/{location}")]
    public IActionResult GetByLocation(string location)
    {
        var items = _store.GetByLocation(location);
        return Ok(items);
    }
}

public class UpdateInventoryRequest
{
    public int? Quantity { get; set; }
    public string? Location { get; set; }
}

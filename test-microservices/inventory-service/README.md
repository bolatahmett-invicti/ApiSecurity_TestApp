# Inventory Service (Ruby/Sinatra)

A simple inventory management microservice built with Ruby and Sinatra.

## Endpoints

### Health Check
- `GET /health` - Service health status

### Inventory Management
- `GET /api/inventory` - Get all inventory items
- `GET /api/inventory/:id` - Get specific inventory item
- `POST /api/inventory` - Create new inventory item
- `PUT /api/inventory/:id` - Update inventory item
- `DELETE /api/inventory/:id` - Delete inventory item

### Operations
- `POST /api/inventory/reserve` - Reserve inventory for an order
- `GET /api/inventory/low-stock?threshold=100` - Get low stock items

### Admin
- `GET /api/admin/inventory/location/:location` - Get inventory by warehouse location

## Running

```bash
bundle install
ruby app.rb
```

Service runs on port 8006.

## Example Requests

```bash
# Get all inventory
curl http://localhost:8006/api/inventory

# Reserve inventory
curl -X POST http://localhost:8006/api/inventory/reserve \
  -H "Content-Type: application/json" \
  -d '{"productId": "prod-001", "quantity": 5}'

# Check low stock
curl http://localhost:8006/api/inventory/low-stock?threshold=100
```

require 'sinatra'
require 'json'

set :port, 8006
set :bind, '0.0.0.0'

# In-memory inventory store
$inventory = {
  'prod-001' => { id: 'prod-001', name: 'Laptop', quantity: 50, location: 'Warehouse A' },
  'prod-002' => { id: 'prod-002', name: 'Mouse', quantity: 200, location: 'Warehouse B' },
  'prod-003' => { id: 'prod-003', name: 'Keyboard', quantity: 150, location: 'Warehouse A' }
}

# Health check endpoint
get '/health' do
  content_type :json
  { status: 'healthy', service: 'inventory-service', timestamp: Time.now.to_i }.to_json
end

# Get all inventory items
get '/api/inventory' do
  content_type :json
  $inventory.values.to_json
end

# Get inventory by product ID
get '/api/inventory/:id' do
  content_type :json
  item = $inventory[params[:id]]
  
  if item
    item.to_json
  else
    status 404
    { error: 'Product not found' }.to_json
  end
end

# Update inventory quantity
put '/api/inventory/:id' do
  content_type :json
  request.body.rewind
  data = JSON.parse(request.body.read, symbolize_names: true)
  
  if $inventory[params[:id]]
    $inventory[params[:id]][:quantity] = data[:quantity] if data[:quantity]
    $inventory[params[:id]][:location] = data[:location] if data[:location]
    $inventory[params[:id]].to_json
  else
    status 404
    { error: 'Product not found' }.to_json
  end
end

# Reserve inventory for an order
post '/api/inventory/reserve' do
  content_type :json
  request.body.rewind
  data = JSON.parse(request.body.read, symbolize_names: true)
  
  product_id = data[:productId]
  quantity = data[:quantity].to_i
  
  item = $inventory[product_id]
  
  if item.nil?
    status 404
    return { error: 'Product not found' }.to_json
  end
  
  if item[:quantity] >= quantity
    item[:quantity] -= quantity
    status 200
    { success: true, reserved: quantity, remaining: item[:quantity] }.to_json
  else
    status 400
    { error: 'Insufficient inventory', available: item[:quantity] }.to_json
  end
end

# Get low stock items
get '/api/inventory/low-stock' do
  content_type :json
  threshold = params[:threshold]&.to_i || 100
  low_stock = $inventory.values.select { |item| item[:quantity] < threshold }
  low_stock.to_json
end

# Admin: Get inventory by location
get '/api/admin/inventory/location/:location' do
  content_type :json
  items = $inventory.values.select { |item| item[:location] == params[:location] }
  items.to_json
end

# Add new inventory item
post '/api/inventory' do
  content_type :json
  request.body.rewind
  data = JSON.parse(request.body.read, symbolize_names: true)
  
  id = data[:id] || "prod-#{rand(1000..9999)}"
  
  $inventory[id] = {
    id: id,
    name: data[:name],
    quantity: data[:quantity].to_i,
    location: data[:location] || 'Warehouse A'
  }
  
  status 201
  $inventory[id].to_json
end

# Delete inventory item
delete '/api/inventory/:id' do
  content_type :json
  
  if $inventory.delete(params[:id])
    { success: true, message: 'Item deleted' }.to_json
  else
    status 404
    { error: 'Product not found' }.to_json
  end
end

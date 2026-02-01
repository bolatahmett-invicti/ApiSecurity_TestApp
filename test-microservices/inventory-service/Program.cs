using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSingleton<InventoryStore>();

var app = builder.Build();

// Configure the HTTP request pipeline
app.MapControllers();

app.Run("http://0.0.0.0:8006");

// In-memory inventory store
public class InventoryStore
{
    private readonly Dictionary<string, InventoryItem> _inventory = new()
    {
        ["prod-001"] = new InventoryItem { Id = "prod-001", Name = "Laptop", Quantity = 50, Location = "Warehouse A" },
        ["prod-002"] = new InventoryItem { Id = "prod-002", Name = "Mouse", Quantity = 200, Location = "Warehouse B" },
        ["prod-003"] = new InventoryItem { Id = "prod-003", Name = "Keyboard", Quantity = 150, Location = "Warehouse A" }
    };

    public IEnumerable<InventoryItem> GetAll() => _inventory.Values;

    public InventoryItem? GetById(string id) => 
        _inventory.TryGetValue(id, out var item) ? item : null;

    public InventoryItem Add(InventoryItem item)
    {
        _inventory[item.Id] = item;
        return item;
    }

    public bool Update(string id, InventoryItem item)
    {
        if (!_inventory.ContainsKey(id)) return false;
        _inventory[id] = item;
        return true;
    }

    public bool Delete(string id) => _inventory.Remove(id);

    public IEnumerable<InventoryItem> GetByLocation(string location) =>
        _inventory.Values.Where(i => i.Location == location);

    public IEnumerable<InventoryItem> GetLowStock(int threshold) =>
        _inventory.Values.Where(i => i.Quantity < threshold);
}

public class InventoryItem
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public int Quantity { get; set; }
    public string Location { get; set; } = string.Empty;
}

public class ReserveRequest
{
    public string ProductId { get; set; } = string.Empty;
    public int Quantity { get; set; }
}

public class ReserveResponse
{
    public bool Success { get; set; }
    public int Reserved { get; set; }
    public int Remaining { get; set; }
    public string? Error { get; set; }
    public int? Available { get; set; }
}

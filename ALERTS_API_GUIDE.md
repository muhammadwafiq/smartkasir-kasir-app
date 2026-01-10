# Stock Alerts API - Quick Reference

## Endpoint
GET /api/manager/stock-alerts

## Authentication
Wajib login dulu via /login

## Contoh Response
```json
{
  "success": true,
  "count": 1,
  "alerts": [
    {
      "name": "Indomie Goreng",
      "currentStock": 10,
      "daysToStockout": 6,
      "urgency": "normal"
    }
  ]
}
```
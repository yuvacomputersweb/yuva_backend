# WhatsApp order messages (WATI)

The website sends a WhatsApp message to the customer at each order stage.
Each message is a **WATI template** in the account the backend uses
(**308273 / +91 97098 88456**). A template must be **approved by WhatsApp**
before it can be sent; until then that one message is skipped and the
failure is recorded in the order's "WhatsApp messages sent" list in the admin.

## Create each template in WATI

WATI → **Broadcast → Template Messages → New Template Message**

- **Category:** Utility  · **Language:** English
- **Template name:** exactly as below (lowercase, underscores)
- Add each variable with **Add variable** and give it exactly the name shown
  (`name`, `order_number`, …). Use the sample values when WATI asks.

### 1. `order_placed`  (probably exists already)
Variables: `name`, `order_number`, `total_price`
```
Hi {{name}}, thank you for your order with Yuva Computers! 🎉

Order number: #{{order_number}}
Order value: {{total_price}}

We're preparing your device and will message you here when it ships.
```

### 2. `payment_received`
Variables: `name`, `order_number`, `amount`
```
Hi {{name}}, we've received your payment of {{amount}} for order #{{order_number}}. ✅

Thank you for shopping with Yuva Computers.
```

### 3. `order_shipped`
Variables: `name`, `order_number`, `tracking_number`, `tracking_url`
```
Hi {{name}}, good news! Your order #{{order_number}} has been shipped with Delhivery.

Tracking number (AWB): {{tracking_number}}
Track your parcel: {{tracking_url}}

Thank you for shopping with Yuva Computers.
```

### 4. `out_for_delivery`
Variables: `name`, `order_number`, `amount_due`
```
Hi {{name}}, your order #{{order_number}} is out for delivery today. 📦

Amount to pay on delivery: {{amount_due}}
Please keep your phone reachable for the delivery partner.
```

### 5. `order_delivered`
Variables: `name`, `order_number`
```
Hi {{name}}, your order #{{order_number}} has been delivered. Enjoy your new device! 💻

You have a 15-day replacement window for any damage or problem — just reply to this message.
Happy with us? Please leave a Google review: https://g.page/r/CaZV-lmS7Y4OEBM/review
```

### 6. `order_cancelled`
Variables: `name`, `order_number`
```
Hi {{name}}, your order #{{order_number}} has been cancelled.

If you paid online, your refund will be processed as per our refund policy.
Questions? Reply here or call 97098 88456.
```

## Renaming or switching off a message

In the server's environment file, set e.g.
`WA_TEMPLATE_ORDER_SHIPPED=my_shipping_template`, or set it to an empty
value to stop that message. Restart gunicorn after changing it.

## When each message is sent

| Message | Sent when |
|---|---|
| order_placed | Payment (or COD advance) succeeds, or admin confirms a COD order |
| payment_received | Payment status becomes **Paid** or **Deposit Paid** |
| order_shipped | Order status becomes **Shipped** (admin, or Delhivery sync) |
| out_for_delivery | Delhivery reports the parcel out for delivery (sync) |
| order_delivered | Order status becomes **Delivered** (admin, or Delhivery sync) |
| order_cancelled | Order status becomes **Cancelled** |

Each message is sent at most once per order. To send one again, use the
admin action **"Resend WhatsApp message for current status"**.

# Eth-Lisbon 2023 hack.

## State transitions - Happy path

```
                    (no message ) ↰
                        ↓          |
    registration -> inbox-wait -> (wait for message) -> (new-message) -> inbox-request -> mech-request -> tx-settlement -> mech-response -> outbox-process-response -> outbox-push -> reset-and-pause -> inbox-wait
```


## Request

### Payload

```json
{
    "address": "0x",  // Wallet address for push notification
    "prompt": "Generate a video of spongebob waving a sign which says '#Olas'",
    "tool": "text-to-video"
}
```

### Example

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"address\": \"0x\", \"prompt\": \"Generate a video of spongebob waving a sign which says '#Olas'\", \"tool\": \"text-to-video\"}" http://localhost:8000/generate
```
# Testum API Examples

This file contains example API requests for testing Testum.

## Prerequisites

Set environment variables:
```bash
export API_URL="http://localhost:8000"
export TOKEN="your-jwt-token"
```

## Authentication

### Login
```bash
curl -X POST $API_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'

# Response:
# {
#   "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "token_type": "bearer"
# }

# Save token
export TOKEN="<access_token>"
```

## Health Check

```bash
curl $API_URL/health

# Response:
# {
#   "status": "healthy",
#   "timestamp": "2025-11-09T12:00:00"
# }
```

## SSH Keys

### Create SSH Key
```bash
curl -X POST $API_URL/api/keys/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-laptop",
    "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDZk... user@laptop"
  }'

# Response:
# {
#   "id": "123e4567-e89b-12d3-a456-426614174000",
#   "name": "my-laptop",
#   "public_key": "ssh-rsa AAAAB3...",
#   "created_by": "admin",
#   "created_at": "2025-11-09T12:00:00"
# }
```

### List SSH Keys
```bash
curl $API_URL/api/keys/

# Response:
# [
#   {
#     "id": "...",
#     "name": "my-laptop",
#     "public_key": "ssh-rsa ...",
#     "created_by": "admin",
#     "created_at": "2025-11-09T12:00:00"
#   }
# ]
```

### Delete SSH Key
```bash
KEY_ID="123e4567-e89b-12d3-a456-426614174000"
curl -X DELETE $API_URL/api/keys/$KEY_ID

# Response:
# {
#   "message": "Key my-laptop deleted successfully"
# }
```

## Platforms

### Create Platform (Password Auth)
```bash
curl -X POST $API_URL/api/platforms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-server-01",
    "host": "192.168.1.100",
    "port": 22,
    "username": "ubuntu",
    "auth_method": "password",
    "password": "MySecretPassword123!"
  }'

# Response:
# {
#   "id": "456e7890-e89b-12d3-a456-426614174001",
#   "name": "web-server-01",
#   "host": "192.168.1.100",
#   "port": 22,
#   "username": "ubuntu",
#   "auth_method": "password",
#   "has_password": true,
#   "has_private_key": false,
#   "known_host_fingerprint": null,
#   "created_at": "2025-11-09T12:00:00"
# }
```

### Create Platform (Private Key Auth)
```bash
curl -X POST $API_URL/api/platforms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "db-server-01",
    "host": "192.168.1.101",
    "port": 22,
    "username": "ubuntu",
    "auth_method": "private_key",
    "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABlwAAAAdzc2gtcn\n...\n-----END OPENSSH PRIVATE KEY-----"
  }'
```

### List Platforms
```bash
curl $API_URL/api/platforms/

# Response:
# [
#   {
#     "id": "...",
#     "name": "web-server-01",
#     "host": "192.168.1.100",
#     "port": 22,
#     "username": "ubuntu",
#     "auth_method": "password",
#     "has_password": true,
#     "has_private_key": false,
#     "known_host_fingerprint": "a1b2c3d4...",
#     "created_at": "2025-11-09T12:00:00"
#   }
# ]
```

### Get Platform
```bash
PLATFORM_ID="456e7890-e89b-12d3-a456-426614174001"
curl $API_URL/api/platforms/$PLATFORM_ID

# Response: Same as create response
```

### Delete Platform
```bash
PLATFORM_ID="456e7890-e89b-12d3-a456-426614174001"
curl -X DELETE $API_URL/api/platforms/$PLATFORM_ID

# Response:
# {
#   "message": "Platform web-server-01 deleted successfully"
# }
```

## Actions

### Deploy All Keys to Platform
```bash
PLATFORM_ID="456e7890-e89b-12d3-a456-426614174001"
curl -X POST $API_URL/api/platforms/$PLATFORM_ID/deploy_keys \
  -H "Content-Type: application/json" \
  -d '{}'

# Response:
# {
#   "task_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
#   "status": "pending",
#   "message": "Key deployment task started"
# }
```

### Deploy Specific Keys to Platform
```bash
PLATFORM_ID="456e7890-e89b-12d3-a456-426614174001"
KEY_ID_1="123e4567-e89b-12d3-a456-426614174000"
KEY_ID_2="789e0123-e89b-12d3-a456-426614174002"

curl -X POST $API_URL/api/platforms/$PLATFORM_ID/deploy_keys \
  -H "Content-Type: application/json" \
  -d "{
    \"key_ids\": [\"$KEY_ID_1\", \"$KEY_ID_2\"]
  }"

# Response: Same as above
```

### Run Command on Platform
```bash
PLATFORM_ID="456e7890-e89b-12d3-a456-426614174001"
curl -X POST $API_URL/api/platforms/$PLATFORM_ID/run_command \
  -H "Content-Type: application/json" \
  -d '{
    "command": "uptime",
    "timeout": 60
  }'

# Response:
# {
#   "task_id": "b2c3d4e5-6789-01bc-defg-234567890abc",
#   "status": "pending",
#   "message": "Command execution task started"
# }
```

### Get Task Status
```bash
TASK_ID="a1b2c3d4-5678-90ab-cdef-1234567890ab"
curl $API_URL/api/tasks/$TASK_ID

# Response:
# {
#   "id": "789e0123-e89b-12d3-a456-426614174003",
#   "celery_task_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
#   "type": "deploy",
#   "platform_id": "456e7890-e89b-12d3-a456-426614174001",
#   "status": "success",
#   "result_location": "platforms/456e7890.../authorized_keys_20251109_120000.txt",
#   "stdout": "Successfully deployed keys. Added 2 new key(s).",
#   "stderr": null,
#   "error_message": null,
#   "started_at": "2025-11-09T12:00:00",
#   "finished_at": "2025-11-09T12:00:05",
#   "created_at": "2025-11-09T12:00:00"
# }
```

## WebSocket Streaming

### Connect to Task Stream (JavaScript)
```javascript
const taskId = 'a1b2c3d4-5678-90ab-cdef-1234567890ab';
const ws = new WebSocket(`ws://localhost:8000/ws/tasks/${taskId}`);

ws.onopen = () => {
  console.log('Connected to task stream');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(`[${message.ts}] [${message.type}] ${message.payload}`);
  
  // Handle different message types
  switch(message.type) {
    case 'progress':
      console.log('Progress:', message.payload);
      break;
    case 'stdout':
      console.log('Output:', message.payload);
      break;
    case 'stderr':
      console.error('Error:', message.payload);
      break;
    case 'done':
      console.log('Task completed:', message.payload);
      ws.close();
      break;
    case 'error':
      console.error('Task failed:', message.payload);
      ws.close();
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from task stream');
};
```

### Connect to Task Stream (Python)
```python
import asyncio
import websockets
import json

async def stream_task(task_id):
    uri = f"ws://localhost:8000/ws/tasks/{task_id}"
    
    async with websockets.connect(uri) as websocket:
        print(f"Connected to task stream: {task_id}")
        
        async for message in websocket:
            data = json.loads(message)
            print(f"[{data['ts']}] [{data['type']}] {data['payload']}")
            
            if data['type'] in ['done', 'error']:
                break

# Run
asyncio.run(stream_task('a1b2c3d4-5678-90ab-cdef-1234567890ab'))
```

## Complete Example Workflow

```bash
#!/bin/bash
# Complete workflow example

API_URL="http://localhost:8000"

echo "1. Login"
TOKEN=$(curl -s -X POST $API_URL/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')
echo "Token: $TOKEN"

echo -e "\n2. Create SSH Key"
KEY_ID=$(curl -s -X POST $API_URL/api/keys/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-key",
    "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ... test@example.com"
  }' | jq -r '.id')
echo "Key ID: $KEY_ID"

echo -e "\n3. Create Platform"
PLATFORM_ID=$(curl -s -X POST $API_URL/api/platforms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-server",
    "host": "192.168.1.100",
    "port": 22,
    "username": "ubuntu",
    "auth_method": "password",
    "password": "testpass"
  }' | jq -r '.id')
echo "Platform ID: $PLATFORM_ID"

echo -e "\n4. Deploy Keys"
TASK_ID=$(curl -s -X POST $API_URL/api/platforms/$PLATFORM_ID/deploy_keys \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r '.task_id')
echo "Task ID: $TASK_ID"

echo -e "\n5. Check Task Status"
sleep 5
curl -s $API_URL/api/tasks/$TASK_ID | jq .

echo -e "\n6. Run Command"
RUN_TASK_ID=$(curl -s -X POST $API_URL/api/platforms/$PLATFORM_ID/run_command \
  -H "Content-Type: application/json" \
  -d '{"command":"uptime","timeout":60}' | jq -r '.task_id')
echo "Run Task ID: $RUN_TASK_ID"

echo -e "\n7. Check Run Task Status"
sleep 3
curl -s $API_URL/api/tasks/$RUN_TASK_ID | jq .

echo -e "\nDone!"
```

## Notes

- All timestamps are in UTC
- Task IDs are Celery task IDs (UUID format)
- Platform credentials are encrypted at rest using Fernet
- SSH host fingerprints are automatically captured on first connection
- WebSocket connections automatically close when task completes

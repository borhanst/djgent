# Persistent Conversation Memory Guide

## Overview

Djgent supports persistent conversation memory using Django models. This allows chat history to persist across sessions, be managed via Django admin, and be associated with users.

## Features

- **Database-backed storage** - Conversations stored in Django models
- **User association** - Link conversations to Django users
- **Django admin integration** - Manage conversations via admin interface
- **Multiple backends** - In-memory (temporary) or database (persistent)
- **Conversation management** - CLI commands for listing, exporting, and cleaning up
- **Resume conversations** - Continue chats from where you left off

## Quick Start

### Basic Usage (In-Memory)

```python
from djgent import Agent

# Default: in-memory storage (temporary)
agent = Agent.create(
    name="assistant",
    memory=True,
)

response = agent.run("Hello!")
```

### Persistent Memory (Database)

```python
from djgent import Agent

# Database-backed persistent storage
agent = Agent.create(
    name="assistant",
    memory=True,
    memory_backend="database",  # Use database backend
)

response = agent.run("Hello!")

# Get conversation ID for later
conv_id = agent.get_conversation_id()
print(f"Conversation ID: {conv_id}")
```

### With User Association

```python
from djgent import Agent

# Associate conversation with a user
agent = Agent.create(
    name="assistant",
    memory_backend="database",
    user=request.user,  # Django user
)

response = agent.run("Hello!")
```

### Resume Existing Conversation

```python
from djgent import Agent

# Resume a previous conversation
agent = Agent.create(
    name="assistant",
    memory_backend="database",
    conversation_id="existing-uuid",  # Resume this conversation
)

response = agent.run("Continuing our previous discussion...")
```

## Configuration

### Settings

Add to your `settings.py`:

```python
DJGENT = {
    # ... other settings
    "MEMORY_BACKEND": "database",  # Default backend
    "MEMORY_SETTINGS": {
        "auto_create": True,       # Auto-create conversation
        "max_messages": 100,       # Max messages to keep
        "cleanup_days": 90,        # Auto-delete old conversations
    },
}
```

## API Reference

### Agent Methods

```python
from djgent import Agent

agent = Agent.create(
    name="assistant",
    memory_backend="database",
    user=request.user,
)

# Get conversation ID
conv_id = agent.get_conversation_id()

# Get conversation info
info = agent.get_conversation_info()
print(f"Messages: {info['message_count']}")
print(f"Created: {info['created_at']}")

# Clear conversation history
agent.clear_memory()

# Get message history
history = agent.get_history()
```

### Memory Utility Functions

```python
from djgent import (
    create_conversation,
    get_conversation,
    delete_conversation,
    get_all_conversations,
)

# Create a conversation
conv_id = create_conversation(
    agent_name="assistant",
    name="My Chat",
    user=request.user,
)

# Get a conversation
conversation = get_conversation(conv_id)
if conversation:
    messages = conversation.messages.all()

# Get all conversations for a user
conversations = get_all_conversations(
    user=request.user,
    agent_name="assistant",
    limit=10,
)

# Delete a conversation
deleted = delete_conversation(conv_id)
```

### Memory Backends

```python
from djgent.memory import get_memory_backend, DatabaseMemory, InMemoryMemory

# Get backend by name
memory = get_memory_backend(
    backend="database",
    agent_name="assistant",
    user=request.user,
)
memory.initialize()

# Or use class directly
memory = DatabaseMemory(
    agent_name="assistant",
    user=request.user,
)
memory.initialize()

# Add messages
memory.add_message("human", "Hello!")
memory.add_message("ai", "Hi there!")

# Get messages
messages = memory.get_messages()
langchain_messages = memory.get_messages_as_langchain()

# Get info
info = memory.get_conversation_info()

# Clear
memory.clear()
```

## Management Commands

### List Conversations

```bash
# List all conversations
python manage.py djgent_list_conversations

# Filter by user
python manage.py djgent_list_conversations --user=admin

# Filter by agent
python manage.py djgent_list_conversations --agent=assistant

# Limit results
python manage.py djgent_list_conversations --limit=10

# Verbose output
python manage.py djgent_list_conversations --verbose
```

### Create Conversation

```bash
# Create new conversation
python manage.py djgent_create_conversation --agent=assistant

# With name
python manage.py djgent_create_conversation --agent=assistant --name="My Chat"

# Associate with user
python manage.py djgent_create_conversation --agent=assistant --user=admin

# With metadata
python manage.py djgent_create_conversation \
    --agent=assistant \
    --user=admin \
    --metadata='{"source": "web", "session_id": "abc123"}'
```

### Export Conversation

```bash
# Export to stdout
python manage.py djgent_export_conversation --id=<uuid>

# Export to file
python manage.py djgent_export_conversation \
    --id=<uuid> \
    --output=conversation.json
```

### Clear Old Conversations

```bash
# Delete conversations older than 30 days
python manage.py djgent_clear_conversations --days=30

# Preview what would be deleted
python manage.py djgent_clear_conversations --days=30 --dry-run

# Filter by user
python manage.py djgent_clear_conversations --days=90 --user=admin

# Filter by agent
python manage.py djgent_clear_conversations --days=30 --agent=assistant
```

## Django Admin

Access conversations via Django admin at `/admin/djgent/`:

- **Conversations** - View, search, and manage all conversations
- **Messages** - View individual messages within conversations

### Admin Features

- Search by conversation name or message content
- Filter by agent name, user, or date
- View message count per conversation
- Export conversation data

## Examples

### Chat Application

```python
from django.shortcuts import render, redirect, get_object_or_404
from djgent import Agent
from djgent.models import Conversation

def chat_view(request):
    # Get or create conversation
    conv_id = request.session.get('conv_id')
    
    if conv_id:
        agent = Agent.create(
            name="assistant",
            memory_backend="database",
            conversation_id=conv_id,
        )
    else:
        agent = Agent.create(
            name="assistant",
            memory_backend="database",
            user=request.user if request.user.is_authenticated else None,
        )
        request.session['conv_id'] = agent.get_conversation_id()
    
    if request.method == 'POST':
        message = request.POST.get('message')
        response = agent.run(message)
        return render(request, 'chat.html', {
            'response': response,
            'history': agent.get_history(),
        })
    
    return render(request, 'chat.html', {
        'history': agent.get_history(),
    })
```

### Multi-User Support

```python
from djgent import Agent, get_all_conversations

def user_conversations(request):
    """Get all conversations for current user."""
    if not request.user.is_authenticated:
        return []
    
    conversations = get_all_conversations(
        user=request.user,
        limit=20,
    )
    return conversations

def continue_conversation(request, conv_id):
    """Continue a specific conversation."""
    conversation = get_object_or_404(
        Conversation,
        id=conv_id,
        user=request.user,  # Ensure ownership
    )
    
    agent = Agent.create(
        name="assistant",
        memory_backend="database",
        conversation_id=conv_id,
        user=request.user,
    )
    
    return agent
```

### Conversation Export

```python
from djgent.memory import export_conversation, import_conversation

def backup_conversation(request, conv_id):
    """Export conversation for backup."""
    data = export_conversation(conv_id, format="json")
    
    response = HttpResponse(data, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename=conversation_{conv_id}.json'
    return response

def restore_conversation(request):
    """Import conversation from backup."""
    if request.method == 'POST':
        data = json.loads(request.FILES['backup'].read())
        
        new_conv_id = import_conversation(
            data,
            user=request.user,
        )
        
        return redirect('chat', conv_id=new_conv_id)
```

## Database Schema

### Conversation Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `name` | CharField | Optional conversation name |
| `agent_name` | CharField | Agent that created this conversation |
| `user` | ForeignKey | Associated Django user (optional) |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |
| `metadata` | JSONField | Additional metadata |

### Message Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | BigAutoField | Primary key |
| `conversation` | ForeignKey | Parent conversation |
| `role` | CharField | 'human', 'ai', or 'system' |
| `content` | TextField | Message content |
| `created_at` | DateTime | Creation timestamp |
| `metadata` | JSONField | Additional metadata |

## Best Practices

1. **Use database backend for production** - In-memory is for testing only
2. **Associate conversations with users** - Enables user-specific history
3. **Clean up old conversations** - Use management command to prevent bloat
4. **Export important conversations** - Backup critical chat history
5. **Use conversation names** - Makes finding conversations easier
6. **Limit message history** - Set `max_messages` to control memory usage

## Troubleshooting

### "Conversation not found"

Ensure you're using the correct conversation ID and the conversation exists:

```python
from djgent import get_conversation

conv = get_conversation(conv_id)
if not conv:
    print("Conversation doesn't exist!")
```

### Messages not persisting

Check that:
1. `memory_backend="database"` is set
2. Migrations are applied: `python manage.py migrate djgent`
3. Database is writable

### Admin not showing conversations

Ensure:
1. `djgent` is in `INSTALLED_APPS`
2. Admin is registered (automatic on app load)
3. User has admin permissions

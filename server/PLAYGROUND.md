# Graphiti API Playground

A web-based interface for testing and visualizing the Graphiti knowledge graph API.

## Features

### 🌐 Graph Visualization (Top Section)
- Interactive knowledge graph display using vis.js
- Real-time updates when new data is added
- Click nodes to see details
- Double-click to focus on a node
- Filter by group ID
- Auto-refresh every 30 seconds

### 🧪 API Testing Interface (Bottom Section)
- **Messages Tab**: Add conversational data to build the knowledge graph
- **Search Tab**: Query facts using semantic search
- **Episodes Tab**: Retrieve conversation history
- **Entity Tab**: Manually add entity nodes
- **Memory Tab**: Get contextual memory based on messages
- **Management Tab**: Delete operations and data clearing

## Access

Open your browser and navigate to: http://localhost:8000

## Quick Start

1. **Add Messages**: Use the Messages tab to add some sample data
2. **View Graph**: The graph visualization will update automatically
3. **Search**: Use the Search tab to find facts
4. **Explore**: Click on nodes in the graph to see details

## API Endpoints

- `POST /messages` - Ingest conversational messages
- `POST /search` - Search for facts in the knowledge graph
- `GET /episodes/{group_id}` - Retrieve episode history
- `POST /entity-node` - Add custom entity nodes
- `POST /get-memory` - Get contextual memory
- `DELETE /group/{group_id}` - Delete a group and all its data
- `DELETE /episode/{uuid}` - Delete a specific episode
- `DELETE /entity-edge/{uuid}` - Delete a specific edge
- `POST /clear` - Clear all data (use with caution!)

## Visualization

The graph uses different colors for different entity types:
- 🟦 Default entities (blue)
- 🟩 People (green)
- 🔴 Organizations (red)
- 🟣 Technology (purple)
- 🟡 Projects (yellow)
- 🔵 Concepts (light blue)

## Tips

- All JSON inputs are automatically formatted on blur
- Press Enter in input fields to execute requests
- Responses are syntax-highlighted for easy reading
- The graph auto-refreshes every 30 seconds
- Use the group filter to focus on specific data sets
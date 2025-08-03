# Troubleshooting Guide - MCP Configuration Issues

## Common Issues and Solutions

### 1. MCP Configuration Schema Validation Errors

**Problem**: 
```
[Failed to parse] Project MCP Config
Location: .mcp.json
└ [Error] mcpServers.<server-name>: Does not adhere to MCP server configuration schema
```

**Root Causes**:
- Server name doesn't match expected conventions
- Missing required fields for the transport type
- Incorrect URL format

**Solutions**:
1. **Check server naming**: Some MCP clients expect specific server names (e.g., `graphiti` instead of custom names)
2. **Verify transport requirements**:
   - SSE transport needs: `transport` and `url` fields
   - STDIO transport needs: `transport`, `command`, `args`, and optionally `env` fields
3. **Validate URL format**: Ensure URLs are properly formatted with protocol (http/https)

### 2. Remote vs Local Configuration Confusion

**Problem**: Documentation shows localhost examples but you need remote server connection

**Understanding**:
- Repository examples default to localhost for development
- Production deployments use remote URLs
- No local services needed for remote MCP servers

**Solution**:
```json
{
  "mcpServers": {
    "graphiti": {
      "transport": "sse",
      "url": "https://your-domain.com/sse"
    }
  }
}
```

### 3. Debugging MCP Connection Issues

**Steps to diagnose**:
1. **Check configuration file location**: Ensure `.mcp.json` is in the project root
2. **Validate JSON syntax**: Use a JSON validator to check for syntax errors
3. **Test endpoint accessibility**: 
   ```bash
   curl -i https://your-domain.com/sse
   ```
4. **Review client logs**: Check MCP client error messages for specific validation failures

### 4. Configuration File Locations

**Where to find examples**:
- SSE example: `mcp_server/mcp_config_sse_example.json`
- STDIO example: `mcp_server/mcp_config_stdio_example.json`
- Docker config: `mcp_server/docker-compose.yml`
- Documentation: `mcp_server/README.md`

### 5. Environment-Specific Configurations

**Development** (STDIO):
- Requires local Python environment
- Uses `uv` package manager
- Needs full paths in configuration

**Production** (SSE):
- Can use remote servers
- No local dependencies
- Simple URL-based configuration

**Docker** (SSE):
- Port 8001 by default (mapped from 8000)
- Includes Neo4j on port 7688
- Environment variables in `.env` file

## Quick Fixes Checklist

- [ ] Is the JSON syntax valid?
- [ ] Is the server name correct? (try `graphiti` if custom names fail)
- [ ] Are all required fields present for your transport type?
- [ ] Is the URL/path format correct?
- [ ] For STDIO: Are paths absolute, not relative?
- [ ] For SSE: Is the endpoint accessible?
- [ ] Is the MCP client version compatible?

## Prevention Tips

1. **Start with examples**: Copy from working examples and modify
2. **Use standard naming**: Stick to `graphiti` unless you need multiple servers
3. **Test incrementally**: Change one field at a time when debugging
4. **Keep backups**: Save working configurations before modifying
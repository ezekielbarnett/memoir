"""
Examples of using the auth system.

This shows how clean and minimal the overhead is.
"""

# =============================================================================
# BEFORE (no auth)
# =============================================================================

"""
@app.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    storage: StorageProvider = Depends(get_storage),
):
    project = await storage.metadata.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
"""

# =============================================================================
# AFTER (with auth) - just add ONE line
# =============================================================================

"""
from memoir.auth import require, AuthContext

@app.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    ctx: AuthContext = Depends(require("project.read")),  # ← This is it!
    storage: StorageProvider = Depends(get_storage),
):
    # ctx.user_id, ctx.project_role, ctx.can() all available
    project = await storage.metadata.get("projects", project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
"""

# =============================================================================
# More examples
# =============================================================================

"""
# Require specific capability
@app.post("/projects/{project_id}/content")
async def add_content(
    project_id: str,
    ctx: AuthContext = Depends(require("content.create")),
):
    # Only users who can create content get here
    ...

# Require any of multiple capabilities
@app.put("/projects/{project_id}/content/{content_id}")
async def edit_content(
    project_id: str,
    content_id: str,
    ctx: AuthContext = Depends(require_any("content.edit", "content.delete")),
):
    ...

# Require minimum tier (paid features)
@app.post("/projects/{project_id}/projections/advanced")
async def create_advanced_projection(
    project_id: str,
    ctx: AuthContext = Depends(require("ai.advanced", min_tier=UserTier.PRO)),
):
    # Only Pro+ users can access
    ...

# Require minimum role
@app.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    ctx: AuthContext = Depends(require("project.delete", min_role=ProjectRole.OWNER)),
):
    # Only project owners can delete
    ...

# Just auth, no specific permission
@app.get("/user/profile")
async def get_profile(ctx: AuthContext = Depends(require_auth())):
    return {"user_id": ctx.user_id, "tier": ctx.user_tier}

# Use context in route logic
@app.get("/projects/{project_id}/content")
async def get_content(
    project_id: str,
    ctx: AuthContext = Depends(require("content.read")),
):
    items = await get_all_content(project_id)
    
    # Conditionally show edit buttons in response
    return {
        "items": items,
        "can_edit": ctx.can("content.edit"),
        "can_delete": ctx.can("content.delete"),
        "user_role": ctx.project_role.value if ctx.project_role else None,
    }
"""

# =============================================================================
# How it works internally
# =============================================================================

"""
1. Request comes in: GET /projects/proj_123/content
   Headers: Authorization: Bearer user_456

2. require("content.read") triggers:
   a. Extract user_id from JWT: "user_456"
   b. Extract project_id from path: "proj_123"
   c. Look up user's role in project: "editor"
   d. Look up user's tier: "pro"
   e. Compute capabilities: {content.read, content.create, ...}
   f. Check if "content.read" in capabilities: YES

3. AuthContext passed to route:
   AuthContext(
       user_id="user_456",
       project_id="proj_123",
       project_role=ProjectRole.EDITOR,
       user_tier=UserTier.PRO,
       _capabilities={...}
   )

4. Route executes with full context available
"""

# =============================================================================
# Testing without real auth
# =============================================================================

"""
For development/testing, you can bypass auth by:

1. Using simple tokens: Authorization: Bearer user_123
   
2. Or adding a test mode in policies.py:
   
   if settings.environment == "development":
       # Auto-grant all permissions
       return AuthContext.system()

3. Or using pytest fixtures that inject AuthContext directly
"""


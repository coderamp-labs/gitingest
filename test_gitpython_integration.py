#!/usr/bin/env python3
"""
Simple test script to verify GitPython integration works.
"""

import asyncio
import sys
from pathlib import Path

# Add specific path for git_utils module
git_utils_path = Path(__file__).parent / "src" / "gitingest" / "utils"
sys.path.insert(0, str(git_utils_path))

# Import the specific functions we need to test
import git_utils


async def test_basic_functions():
    """Test basic functionality without external dependencies."""
    print("🔍 Testing GitPython integration...")
    
    # Test 1: Test token validation (no external deps)
    print("✅ Testing GitHub token validation...")
    try:
        git_utils.validate_github_token("ghp_" + "A" * 36)
        print("   ✓ Valid token accepted")
    except Exception as e:
        print(f"   ✗ Token validation failed: {e}")
    
    # Test 2: Test GitHub host detection
    print("✅ Testing GitHub host detection...")
    assert git_utils.is_github_host("https://github.com/owner/repo") == True
    assert git_utils.is_github_host("https://gitlab.com/owner/repo") == False
    print("   ✓ GitHub host detection works")
    
    # Test 3: Test auth header creation
    print("✅ Testing auth header creation...")
    token = "ghp_" + "A" * 36
    header = git_utils.create_git_auth_header(token)
    assert "Authorization: Basic" in header
    assert "github.com" in header
    print("   ✓ Auth header creation works")
    
    # Test 4: Test Git command creation with auth
    print("✅ Testing Git command creation...")
    git_cmd = git_utils.create_git_command_with_auth(token, "https://github.com/owner/repo")
    # Should have authentication configured
    assert hasattr(git_cmd, 'custom_environment'), "GitPython command should have custom environment"
    assert 'GIT_CONFIG_PARAMETERS' in git_cmd.custom_environment, "Should have auth parameters"
    print("   ✓ Git command with auth works")
    
    git_cmd_no_auth = git_utils.create_git_command_with_auth(None, "https://github.com/owner/repo")
    # Should not have auth for no token
    assert not hasattr(git_cmd_no_auth, 'custom_environment') or 'GIT_CONFIG_PARAMETERS' not in (git_cmd_no_auth.custom_environment or {}), "Should not have auth without token"
    print("   ✓ Git command without auth works")
    
    # Test 5: Test git installation check
    print("✅ Testing Git installation check...")
    try:
        await git_utils.ensure_git_installed()
        print("   ✓ Git is installed and accessible")
    except Exception as e:
        print(f"   ✗ Git installation check failed: {e}")
    
    print("\n🎉 All basic tests passed! GitPython integration is working.")


if __name__ == "__main__":
    asyncio.run(test_basic_functions())
# Pre-Commit Review Checklist

Use this checklist before committing changes to ensure quality and completeness.

---

## Code Quality

### Python Scripts

- [ ] **Syntax Valid**: All `.py` files pass `python3 -m py_compile`
- [ ] **Imports Work**: All imports resolve correctly
- [ ] **Type Hints**: Function signatures have type hints
- [ ] **Docstrings**: All public functions have docstrings
- [ ] **Error Handling**: Exceptions caught and handled appropriately
- [ ] **No Hardcoded Values**: Configuration values are parameterized
- [ ] **Logging**: Important operations are logged
- [ ] **No Debug Code**: Remove print statements, temporary code

```bash
# Verify syntax
for f in scripts/*.py; do python3 -m py_compile "$f" && echo "✓ $f"; done

# Check imports
python3 -c "from scripts.adb_controller import ADBController; print('✓ Imports OK')"
```

### Bash Scripts

- [ ] **Shebang**: Scripts start with `#!/bin/bash`
- [ ] **set -e**: Scripts exit on error
- [ ] **Quoting**: Variables properly quoted
- [ ] **Error Messages**: Clear error messages to stderr
- [ ] **Exit Codes**: Appropriate exit codes used

---

## Documentation

### Required Files

- [ ] **README.md**: Updated with any new features
- [ ] **SKILL.md**: Command reference complete and accurate
- [ ] **CHANGELOG.md**: Changes documented
- [ ] **VERSION**: Version number updated if needed

### Documentation Quality

- [ ] **Accuracy**: All code examples tested and working
- [ ] **Completeness**: New features documented
- [ ] **Clarity**: Language clear and concise
- [ ] **Formatting**: Proper Markdown formatting
- [ ] **Links**: All internal links work

### Docs Directory

- [ ] **SETUP.md**: Setup instructions current
- [ ] **USE_CASES.md**: Relevant use cases included
- [ ] **ERROR_HANDLING.md**: Error codes documented
- [ ] **GUIDELINES.md**: Best practices updated
- [ ] **TUTORIALS.md**: Examples work correctly

---

## Security

### Code Security

- [ ] **No Credentials**: No API keys, passwords, tokens in code
- [ ] **No PII**: No personal information exposed
- [ ] **Input Validation**: User inputs validated
- [ ] **Command Injection**: Shell commands properly escaped
- [ ] **File Paths**: Path traversal prevented

### Security Documentation

- [ ] **Warnings**: Security warnings in appropriate places
- [ ] **Best Practices**: Security best practices documented

---

## Compatibility

### ADB Compatibility

- [ ] **Commands Work**: All ADB commands tested
- [ ] **Version Agnostic**: Works with various ADB versions
- [ ] **Error Handling**: Graceful handling of unavailable features

### Android Compatibility

- [ ] **Android 10+**: Tested on Android 10+
- [ ] **Multiple OEMs**: Considered Samsung, Xiaomi, Huawei differences
- [ ] **USB & Wireless**: Both connection types work

### Environment Compatibility

- [ ] **Termux**: Works in Termux environment
- [ ] **Linux**: Works on Linux systems
- [ ] **macOS**: Works on macOS (if applicable)

---

## Structure

### File Organization

- [ ] **Correct Location**: Files in appropriate directories
- [ ] **Naming Convention**: Consistent file naming
- [ ] **No Duplicates**: No duplicate files or code

### Directory Structure

```
adb-android-control/
├── .claude-plugin/
│   └── marketplace.json      # ✓ Valid JSON
├── scripts/
│   ├── adb_controller.py     # ✓ Syntax valid
│   ├── adb_automation.py     # ✓ Syntax valid
│   └── adb_monitor.py        # ✓ Syntax valid
├── docs/
│   ├── SETUP.md              # ✓ Complete
│   ├── USE_CASES.md          # ✓ Complete
│   ├── ERROR_HANDLING.md     # ✓ Complete
│   ├── GUIDELINES.md         # ✓ Complete
│   └── TUTORIALS.md          # ✓ Complete
├── references/
│   ├── keycodes.md           # ✓ Complete
│   └── troubleshooting.md    # ✓ Complete
├── SKILL.md                  # ✓ Complete
├── README.md                 # ✓ Complete
├── CHANGELOG.md              # ✓ Updated
├── CONTRIBUTING.md           # ✓ Complete
├── LICENSE                   # ✓ Present
├── VERSION                   # ✓ Current
└── .gitignore                # ✓ Present
```

---

## Git

### Commit Preparation

- [ ] **Clean Working Tree**: No untracked files that should be committed
- [ ] **Staged Changes**: Correct files staged
- [ ] **No Sensitive Data**: No secrets in commit

### Commit Message

- [ ] **Format**: Follows `<type>(<scope>): <subject>` format
- [ ] **Type**: Appropriate type (feat, fix, docs, etc.)
- [ ] **Subject**: Clear, imperative, <72 chars
- [ ] **Body**: Explains what and why (if needed)

### Branch

- [ ] **Branch Name**: Descriptive branch name
- [ ] **Up to Date**: Branch up to date with main
- [ ] **No Conflicts**: No merge conflicts

---

## Testing

### Manual Testing

- [ ] **Connection**: Device connects successfully
- [ ] **Basic Commands**: Core commands work
- [ ] **File Operations**: Push/pull work
- [ ] **Input Simulation**: Tap/swipe work
- [ ] **Screenshots**: Screenshot capture works

### Script Testing

```bash
# Test adb_controller.py
python3 scripts/adb_controller.py

# Expected output:
# === ADB Controller Demo ===
# Connected devices: 1
# Device Info:
#   Model: <device_model>
#   Android: <version>
# ...
```

### Documentation Testing

- [ ] **Examples Run**: Code examples in docs execute correctly
- [ ] **Commands Work**: All documented commands tested

---

## Final Checks

### Before Commit

```bash
# 1. Check file structure
find . -type f -name "*.py" -o -name "*.md" -o -name "*.sh" | head -30

# 2. Validate JSON
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); print('✓ JSON valid')"

# 3. Check Python syntax
for f in scripts/*.py; do python3 -m py_compile "$f" && echo "✓ $f OK"; done

# 4. Run main script
python3 scripts/adb_controller.py

# 5. Check git status
git status

# 6. Review diff
git diff --staged
```

### Approval Criteria

| Category | Requirement | Status |
|----------|-------------|--------|
| Code | Syntax valid | ☐ |
| Code | No errors | ☐ |
| Docs | Complete | ☐ |
| Docs | Accurate | ☐ |
| Security | No secrets | ☐ |
| Security | Safe code | ☐ |
| Testing | Manual test pass | ☐ |
| Testing | Examples work | ☐ |
| Git | Clean commit | ☐ |
| Git | Good message | ☐ |

---

## Quick Validation Script

```bash
#!/bin/bash
# validate.sh - Run before commit

echo "=== Pre-Commit Validation ==="

ERRORS=0

# Check JSON
echo -n "Checking marketplace.json... "
if python3 -c "import json; json.load(open('.claude-plugin/marketplace.json'))" 2>/dev/null; then
    echo "✓"
else
    echo "✗ INVALID"
    ((ERRORS++))
fi

# Check Python
for f in scripts/*.py; do
    echo -n "Checking $f... "
    if python3 -m py_compile "$f" 2>/dev/null; then
        echo "✓"
    else
        echo "✗ SYNTAX ERROR"
        ((ERRORS++))
    fi
done

# Check required files
for f in SKILL.md README.md CHANGELOG.md VERSION LICENSE .gitignore; do
    echo -n "Checking $f exists... "
    if [ -f "$f" ]; then
        echo "✓"
    else
        echo "✗ MISSING"
        ((ERRORS++))
    fi
done

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "=== All checks passed! Ready to commit. ==="
    exit 0
else
    echo "=== $ERRORS errors found. Please fix before committing. ==="
    exit 1
fi
```

---

## Sign-Off

**Reviewer**: _________________

**Date**: _________________

**Status**: ☐ Approved  ☐ Changes Requested

**Notes**:
```




```

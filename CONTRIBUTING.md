# Contributing to ADB Android Control

Thank you for your interest in contributing to ADB Android Control! This document provides guidelines and instructions for contributing.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [How to Contribute](#how-to-contribute)
4. [Development Setup](#development-setup)
5. [Coding Standards](#coding-standards)
6. [Commit Guidelines](#commit-guidelines)
7. [Pull Request Process](#pull-request-process)
8. [Documentation](#documentation)
9. [Testing](#testing)
10. [Review Process](#review-process)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors.

### Standards

- Use welcoming and inclusive language
- Be respectful of differing viewpoints
- Accept constructive criticism gracefully
- Focus on what is best for the community

### Enforcement

Unacceptable behavior may be reported to the maintainers.

---

## Getting Started

### Prerequisites

- Git installed
- ADB installed (`pkg install android-tools` on Termux)
- Python 3.8+ (for scripts)
- Android device with USB/Wireless debugging enabled

### Fork and Clone

```bash
# Fork the repository on GitHub

# Clone your fork
git clone https://github.com/YOUR_USERNAME/adb-android-control.git
cd adb-android-control

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/adb-android-control.git
```

---

## How to Contribute

### Types of Contributions

#### 1. Bug Reports

Found a bug? Open an issue with:
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Device info (model, Android version)
- ADB version (`adb version`)

#### 2. Feature Requests

Have an idea? Open an issue with:
- Clear description of the feature
- Use case / why it's useful
- Possible implementation approach

#### 3. Documentation

Help improve docs:
- Fix typos or unclear explanations
- Add examples
- Translate to other languages
- Add tutorials

#### 4. Code Contributions

- Fix bugs
- Implement new features
- Improve performance
- Add tests

---

## Development Setup

### Environment Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/adb-android-control.git
cd adb-android-control

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install pytest black flake8 mypy
```

### Verify Setup

```bash
# Check ADB
adb version

# Check Python scripts syntax
python3 -m py_compile scripts/adb_controller.py
python3 -m py_compile scripts/adb_automation.py
python3 -m py_compile scripts/adb_monitor.py

# Run basic test
python3 scripts/adb_controller.py
```

---

## Coding Standards

### Python Code

#### Style Guide

Follow PEP 8 with these specifics:

```python
# Good: Clear, descriptive names
def get_device_battery_level() -> int:
    """Get current battery level percentage."""
    pass

# Bad: Unclear names
def get_bat():
    pass
```

#### Type Hints

Use type hints for function signatures:

```python
from typing import Optional, List, Dict

def install_apk(
    apk_path: str,
    replace: bool = True,
    grant_permissions: bool = False
) -> bool:
    """Install APK on device."""
    pass
```

#### Docstrings

Use Google-style docstrings:

```python
def tap(x: int, y: int, duration_ms: int = 0) -> None:
    """
    Simulate tap at screen coordinates.

    Args:
        x: Horizontal coordinate (pixels from left)
        y: Vertical coordinate (pixels from top)
        duration_ms: Long press duration (0 for normal tap)

    Raises:
        ADBError: If device not connected

    Example:
        >>> adb.tap(540, 1200)
        >>> adb.tap(540, 1200, duration_ms=1000)  # Long press
    """
    pass
```

#### Error Handling

```python
# Good: Specific exceptions with context
try:
    result = subprocess.run(cmd, capture_output=True, timeout=30)
except subprocess.TimeoutExpired:
    raise ADBError(f"Command timed out: {' '.join(cmd)}")
except FileNotFoundError:
    raise ADBError("ADB not found. Is it installed?")

# Bad: Generic exception handling
try:
    result = subprocess.run(cmd)
except:
    pass
```

### Bash Scripts

```bash
#!/bin/bash
# Script description
# Usage: script.sh <arg1> <arg2>

set -e  # Exit on error

# Constants in UPPER_CASE
readonly TIMEOUT=30

# Functions with descriptive names
check_device_connection() {
    if ! adb devices | grep -q "device$"; then
        echo "Error: No device connected" >&2
        return 1
    fi
}

# Main logic
main() {
    check_device_connection || exit 1
    # ... rest of script
}

main "$@"
```

### Documentation

- Use Markdown
- Include code examples
- Keep language clear and concise
- Add table of contents for long documents

---

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no code change
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

### Examples

```
feat(input): add multi-touch gesture support

Add support for simulating multi-touch gestures using
the input event system.

Closes #123
```

```
fix(connection): handle device disconnect gracefully

Previously, disconnect during file transfer caused crash.
Now properly catches exception and reports error.

Fixes #456
```

```
docs(setup): add Samsung-specific instructions

Add detailed steps for enabling debugging on Samsung
devices with Knox.
```

### Rules

- Use imperative mood ("add" not "added")
- First line max 72 characters
- Body wrapped at 72 characters
- Reference issues when applicable

---

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Self-reviewed changes
- [ ] Added/updated documentation
- [ ] Added tests if applicable
- [ ] All tests pass
- [ ] Commits are clean and well-described

### Submitting PR

1. Create feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make changes and commit:
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

3. Push to your fork:
   ```bash
   git push origin feature/my-feature
   ```

4. Open PR on GitHub

### PR Description Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Other (describe)

## Testing
Describe how you tested the changes.

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass

## Related Issues
Closes #XXX
```

---

## Documentation

### Where to Document

| Type | Location |
|------|----------|
| Command reference | SKILL.md |
| Setup instructions | docs/SETUP.md |
| Use cases | docs/USE_CASES.md |
| Error handling | docs/ERROR_HANDLING.md |
| Best practices | docs/GUIDELINES.md |
| Tutorials | docs/TUTORIALS.md |
| API reference | Code docstrings |

### Documentation Standards

- Clear, concise language
- Working code examples
- Tested commands
- Updated for all changes

---

## Testing

### Running Tests

```bash
# Test Python syntax
python3 -m py_compile scripts/*.py

# Test imports
python3 -c "from scripts.adb_controller import ADBController"

# Run script tests
python3 scripts/adb_controller.py
```

### Testing Checklist

- [ ] Basic connection works
- [ ] Commands execute correctly
- [ ] Error handling works
- [ ] Documentation examples work
- [ ] Edge cases handled

### Device Testing

Test on multiple:
- Android versions (10, 11, 12, 13, 14)
- Manufacturers (Samsung, Pixel, Xiaomi, etc.)
- Connection types (USB, wireless)

---

## Review Process

### Review Checklist

#### Code Quality
- [ ] Follows coding standards
- [ ] No unnecessary complexity
- [ ] Proper error handling
- [ ] No hardcoded values
- [ ] No security issues

#### Documentation
- [ ] Public functions documented
- [ ] Examples provided
- [ ] README updated if needed

#### Testing
- [ ] Changes tested
- [ ] Edge cases considered
- [ ] No regressions

#### Compatibility
- [ ] Works with multiple Android versions
- [ ] Works with USB and wireless
- [ ] No breaking changes

### Review Timeline

- Initial review: 1-3 days
- Follow-up: 1-2 days after updates
- Merge: After approval

---

## Questions?

- Open an issue for questions
- Tag with "question" label
- Check existing issues first

Thank you for contributing!

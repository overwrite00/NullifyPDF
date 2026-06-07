---
name: 🐛 Bug Report
description: Report a bug or issue you've encountered
title: "[BUG] "
labels: ["bug"]
assignees: []
---

## 📝 Description

A clear and concise description of what the bug is. What did you expect to happen? What happened instead?

## 🔄 Steps to Reproduce

Please provide clear steps to reproduce the bug:

1. Load PDF: [file name or type]
2. Click: [button or action]
3. Select: [option]
4. See: [error or unexpected behavior]

## 🖼️ Screenshots

If applicable, add screenshots to help explain your problem.

```
Paste screenshot here
```

## 💻 Environment

Please fill in the following:

- **OS:** [Windows 10/11, macOS 12/13, Ubuntu 22.04, etc.]
- **Python Version:** [Output of `python --version`]
- **NullifyPDF Version:** [v2.0.5, v2.0.4, etc.]
- **PDF Type:** [Native PDF, Scanned PDF, Encrypted, etc.]

## 📊 Log Output

Please share relevant log output:

1. Enable debug mode:
   - **Windows:** `$env:NULLIFYPDF_DEBUG = "true"` then run
   - **macOS/Linux:** `export NULLIFYPDF_DEBUG=true` then run

2. Reproduce the bug

3. Copy logs from: `~/.nullifypdf/logs/nullifypdf.log`

```
Paste logs here (feel free to remove sensitive info)
```

## ✅ Checklist

- [ ] I have verified this is not already reported
- [ ] I am using the latest version of NullifyPDF
- [ ] I can reproduce this bug consistently
- [ ] I have included debug logs or error messages
- [ ] I have removed sensitive information from logs/screenshots

## 📌 Additional Context

Any other context about the problem? For example:
- PDF file size or page count
- Presence of images or special formatting
- Concurrent application usage
- Recent system changes

---

**Thank you for helping improve NullifyPDF!** 🙏

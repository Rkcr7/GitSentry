# Contributing to GitSentry

Thank you for your interest in contributing to GitSentry! We welcome contributions from the community to make this tool better and more effective.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct, which promotes a respectful and inclusive environment for all contributors.

## How Can I Contribute?

There are many ways you can contribute to this project:

### Reporting Bugs

If you encounter a bug while using GitSentry, please:

1. Check if the bug has already been reported in the Issues section.
2. If not, create a new issue with a clear description of the bug, including:
   - Steps to reproduce the issue
   - Expected behavior
   - Actual behavior
   - Screenshots (if applicable)
   - Environment information (OS, Python version, etc.)

### Suggesting Enhancements

Have an idea to improve GitSentry? We'd love to hear it!

1. Check if your enhancement idea has already been suggested in the Issues section.
2. If not, create a new issue with:
   - A clear title and description of your idea
   - Explain why this enhancement would be useful to most users
   - Suggest an implementation approach if possible

### Adding Token Patterns

One of the most valuable contributions is adding new token patterns to detect additional types of exposed credentials:

1. Test your regex pattern thoroughly to ensure it correctly identifies the target tokens without excessive false positives.
2. Add your pattern to `token_patterns.json` with a descriptive name.
3. Submit a pull request with:
   - The new pattern
   - A brief explanation of what the pattern detects
   - Example matches (with fake tokens) to demonstrate its effectiveness

### Pull Requests

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Make your changes, with clear commit messages
4. Update documentation as needed
5. Submit a pull request with a description of your changes

## Development Setup

1. Clone your fork of the repository
2. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your GitHub token for testing:
   ```
   GITHUB_TOKEN=your_github_token_here
   ```

## Coding Guidelines

- Follow PEP 8 style guidelines for Python code
- Write clear, descriptive commit messages
- Add comments to explain complex logic
- Write docstrings for new functions/methods
- Maintain consistent error handling and logging

## Testing

- Test your changes thoroughly before submitting a pull request
- If adding new functionality, include examples of how to use it

## Documentation

- Update the README.md if your changes require users to do something differently
- Document new features or changed behavior

## Ethical Considerations

As GitSentry is a security tool, please consider the ethical implications of your contributions:

- Don't add features that could encourage abuse or misuse
- Prioritize privacy and security concerns in your implementation
- Consider how your contribution might be used both constructively and destructively

## Questions?

If you have any questions about contributing, please open an issue with your question and we'll do our best to help.

Thank you for contributing to GitSentry! 
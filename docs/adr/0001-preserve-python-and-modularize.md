# Preserve Python and wxPython Runtime for Modular Refactoring

## Context
The application (`tasks_app.py`) is a 1270-line Python script utilizing `wxPython` for native Win32 accessibility (NVDA screen reader support) and local text/JSON persistence. We evaluated rewriting the application in a compiled native language (such as C#, Go, or C++) to reduce binary size and startup latency.

## Decision
We decided to retain Python and `wxPython`, focusing effort entirely on modular refactoring and decoupling internal logic into deep modules rather than rewriting the codebase in another programming language.

## Rationale & Trade-offs
Rewriting in a native compiled language would jeopardize the thoroughly verified Win32 accessibility and NVDA screen reader integration, which is the primary value proposition of this application. Python + wxPython provides native platform accessibility controls out-of-the-box. Architectural friction in the codebase stems from mixing UI event loops with storage and business logic in a monolithic file, which can be fully resolved through modular refactoring within Python without the high cost and risks of a multi-language rewrite.

# Data Engineering Journey

🌐 **English** | [Tiếng Việt](README.vi.md)

My hands-on path to becoming a data engineer: one folder per project, each with the code, the result, and **the process that got there**, including the bugs, wrong turns and fixes along the way.

## Projects

| # | Project | Tools | Status |
|---|---|---|---|
| 01 | [TMDB movie data analysis with the Linux command line](project_01/) | Bash, `awk`, `sort`, `cut`, `uniq`... | ✅ Done |
| 02 | [Tiki product scraper: ~200,000 products from an API to JSON](project_02/) · [step-by-step guide](project_02/GUIDE.md) | Python, `requests`, BeautifulSoup, `tmux`, Git | 🚧 In progress |

## How each project is documented

- **README**: the problem, the result, and how to run it.
- **Process over polish**: each project keeps the mistakes I hit and how I solved them, because that is where most of the learning happened.
- **Step-by-step guides** (from Project 02): the solution is built level by level, starting from the simplest working version. Each level begins with a problem to think about before the solution is shown.

## Repository structure

```
data-engineering-journey/
├── project_01/     # TMDB – Linux CLI
├── project_02/     # Tiki scraper – Python
└── .gitignore      # shared rules: data files, outputs and virtual environments stay out of Git
```

Raw data and generated output are **not** committed. Each project README explains how to get or regenerate them.

## Skills practiced so far

- **Linux & shell**: file system navigation, text processing pipelines, `tmux`, processes, logs
- **Data extraction**: calling REST APIs, rate limiting, handling blocks and errors
- **Data cleaning**: HTML to text, deduplication, validation of inputs
- **Pipeline reliability**: batching, checkpoints, atomic writes, resumable runs, reconciliation checks
- **Git & GitHub**: commits, `.gitignore`, renaming and restructuring a repository without losing history

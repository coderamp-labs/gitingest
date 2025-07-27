# Contributing to Gitingest

Thanks for your interest in contributing to **Gitingest** 🚀 Our goal is to keep the codebase friendly to first-time contributors.
If you ever get stuck, reach out on [Discord](https://discord.com/invite/zerRaGK9EC).

---

## How to Contribute (non-technical)

- **Create an Issue** – found a bug or have a feature idea?
  [Open an issue](https://github.com/coderamp-labs/gitingest/issues/new).
- **Spread the Word** – tweet, blog, or tell a friend.
- **Use Gitingest** – real-world usage gives the best feedback. File issues or ping us on [Discord](https://discord.com/invite/zerRaGK9EC) with anything you notice.

---

## Git Strategy

The idea is to follow basic "trunk based development" strategy.

We consider that the `main` branch is the one that is production ready and always up to date.

When submitting a PR for review, the history should be clean and linear, containing **only** the changes that are being reviewed. Thus, if there are changes on the target branch, the PR should be rebased on top of it. This makes it easier to both review and understand the changes, reducing overall overhead. Consider the history to be part of the PR, not just a side-effect of git.

If there are conflicts, they will then have to be resolved locally.

When merging a PR, we will use the `squash` option with a linear history, reducing the entire PR into a single commit. This will force PRs to focus on one feature or bug fix at a time.

**tldr:**

- PRs should be *rebased* on the target branch
- target branch should *not* be merged back into the PR
- only tackle one thing at a time

**NB:** There is currently a bug in GitHub where using the `rebase` option on the website will remove the gpg signature of the commits. They don't seem to be planning on fixing it so we will need to do it locally and then force-push the PR.

---

## How to submit a Pull Request

> **Prerequisites**: The project uses **Python 3.9+** and `pre-commit` for development.

1. **Fork** the repository.

2. **Clone** your fork:

   ```bash
   git clone https://github.com/coderamp-labs/gitingest.git
   cd gitingest
   ```

3. **Set up the dev environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev,server]"
   pre-commit install
   ```

4. **Create a branch** for your changes.

5. **Make your changes** (and add tests when relevant).

6. Run the local server and tests to sanity-check (these will run automatically in the CI/CD pipelines, but it's good to check locally as well)

7. **Sign** your commits and push your branch.

8. **Open a pull request** on GitHub with a clear description of your changes.

9. **Iterate** on any feedback you receive.

*(Optional) Invite a maintainer to your branch for easier collaboration.*

Do not hesitate to ask for help if you get stuck, either here or on the Discord server.

Keep in mind that we are a small team and we will do our best to review your changes as soon as possible.

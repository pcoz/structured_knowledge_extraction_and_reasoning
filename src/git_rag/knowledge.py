"""Git knowledge base — structured RAG corpus for the enterprise demo.

The enterprise RAG wedge case: a developer asks "how do I X with Git?"
and gets back a verified, sourced, copy-pasteable answer. Unlike an
LLM "answering Git questions", every claim here is traceable to a
specific section of the Git manual (git-scm.com/docs).

This is the structured-extraction equivalent of vector RAG:
  - Vector RAG: embed manual chunks → cosine-similar retrieval → LLM
    synthesises an answer (may hallucinate, no provenance)
  - This RAG: structured facts (action / commands / explanation /
    source) → topic-matched retrieval → deterministic rendering
    (cannot hallucinate, provenance per fact)

Each KnowledgeItem captures one usable piece of Git lore:
  - topic / subtopic / intent: cell-grammar-style retrieval keys
  - commands: the actual shell commands to run
  - explanation: human-readable description
  - cautions: gotchas to flag
  - source: section of the Git manual
  - related_items: cross-links for follow-up questions

In production an AI extractor would generate this corpus from the
full Git manual. Here it's hand-curated as the demo's
construction-time AI step.
"""

from dataclasses import dataclass, field


@dataclass
class KnowledgeItem:
    item_id: str
    topic: str                                                # commit, branch, merge, rebase, ...
    subtopic: str                                             # undo, create, list, fix, ...
    intent: str                                               # how-to, what-is, why, compare
    question_patterns: list[str]                              # how the user might phrase it
    commands: list[str] = field(default_factory=list)
    explanation: str = ""
    cautions: list[str] = field(default_factory=list)
    source: str = ""                                          # manual section
    related_items: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# The knowledge base. ~40 entries covering the most common Git
# operations. Each is verifiable against git-scm.com/docs.
# ----------------------------------------------------------------------


GIT_KB: list[KnowledgeItem] = [

    # ----- COMMIT operations -----

    KnowledgeItem(
        item_id="commit.undo_last_unpushed",
        topic="commit", subtopic="undo", intent="how-to",
        question_patterns=[
            "undo last commit", "undo my last commit",
            "remove last commit", "delete last commit", "revert last commit",
        ],
        commands=[
            "git reset --soft HEAD~1   # keep changes staged",
            "git reset HEAD~1          # keep changes unstaged",
            "git reset --hard HEAD~1   # discard changes (DANGEROUS)",
        ],
        explanation=(
            "Use `git reset` with the appropriate mode. --soft keeps "
            "your changes staged for re-commit; default mode unstages "
            "them; --hard discards them entirely. Only use these if "
            "the commit has NOT been pushed."
        ),
        cautions=[
            "If the commit was already pushed, use `git revert` "
            "instead — `git reset --hard` rewrites history.",
            "`--hard` is destructive and cannot be undone via Git.",
        ],
        source="git-scm.com/docs/git-reset",
        related_items=["commit.revert_pushed", "commit.amend"],
    ),

    KnowledgeItem(
        item_id="commit.revert_pushed",
        topic="commit", subtopic="undo", intent="how-to",
        question_patterns=[
            "revert pushed commit", "undo commit already pushed",
            "rollback pushed commit",
        ],
        commands=[
            "git revert <commit-sha>",
            "git push",
        ],
        explanation=(
            "`git revert` creates a NEW commit that undoes the changes "
            "of the named commit, preserving history. Safe to use on "
            "shared / pushed branches."
        ),
        cautions=[
            "If the commit is a merge commit, use "
            "`git revert -m 1 <sha>` to specify the mainline parent.",
        ],
        source="git-scm.com/docs/git-revert",
        related_items=["commit.undo_last_unpushed"],
    ),

    KnowledgeItem(
        item_id="commit.amend",
        topic="commit", subtopic="amend", intent="how-to",
        question_patterns=[
            "amend commit", "fix last commit message",
            "add file to previous commit",
            "modify last commit",
        ],
        commands=[
            "git commit --amend                  # opens editor for message",
            'git commit --amend -m "new message" # set message directly',
            "git commit --amend --no-edit        # keep message, add staged changes",
        ],
        explanation=(
            "`git commit --amend` replaces the last commit with a new "
            "one that includes any currently staged changes and/or a "
            "modified commit message. The previous commit is "
            "discarded (rewriting history)."
        ),
        cautions=[
            "Don't amend commits that have been pushed; it rewrites "
            "history and breaks anyone who's pulled the old version.",
        ],
        source="git-scm.com/docs/git-commit#Documentation/git-commit.txt---amend",
        related_items=["commit.undo_last_unpushed"],
    ),

    # ----- BRANCH operations -----

    KnowledgeItem(
        item_id="branch.create",
        topic="branch", subtopic="create", intent="how-to",
        question_patterns=[
            "create branch", "make a new branch", "new branch",
            "start a branch",
        ],
        commands=[
            "git checkout -b <new-branch>           # create + switch",
            "git switch -c <new-branch>             # modern alias",
            "git branch <new-branch>                # create without switching",
        ],
        explanation=(
            "Creates a new branch off the current HEAD. `checkout -b` "
            "is the classical form; `switch -c` is the modern "
            "equivalent (Git 2.23+)."
        ),
        source="git-scm.com/docs/git-branch",
        related_items=["branch.switch", "branch.list"],
    ),

    KnowledgeItem(
        item_id="branch.delete_local",
        topic="branch", subtopic="delete", intent="how-to",
        question_patterns=[
            "delete branch", "delete local branch", "remove branch",
            "delete a branch I'm done with",
        ],
        commands=[
            "git branch -d <branch-name>   # safe delete (refuses if unmerged)",
            "git branch -D <branch-name>   # force delete (DANGEROUS — discards unmerged work)",
        ],
        explanation=(
            "`-d` deletes a branch only if it has been fully merged "
            "into its upstream or current branch. `-D` (capital) "
            "force-deletes even if there are unmerged commits."
        ),
        cautions=[
            "Use `-D` only when you're sure the unmerged work is "
            "actually disposable.",
            "Cannot delete the branch you're currently on; check out "
            "another branch first.",
        ],
        source="git-scm.com/docs/git-branch#Documentation/git-branch.txt--d",
        related_items=["branch.delete_remote"],
    ),

    KnowledgeItem(
        item_id="branch.delete_remote",
        topic="branch", subtopic="delete", intent="how-to",
        question_patterns=[
            "delete remote branch", "remove branch from remote",
            "delete branch on github",
        ],
        commands=[
            "git push origin --delete <branch-name>",
            "git push origin :<branch-name>             # older syntax",
        ],
        explanation=(
            "Deletes a branch on the remote (typically `origin`). The "
            "local copy is untouched; delete it separately with "
            "`git branch -d`."
        ),
        source="git-scm.com/docs/git-push",
        related_items=["branch.delete_local"],
    ),

    KnowledgeItem(
        item_id="branch.rename",
        topic="branch", subtopic="rename", intent="how-to",
        question_patterns=[
            "rename branch", "change branch name",
            "rename current branch",
        ],
        commands=[
            "git branch -m <old> <new>     # rename a specific branch",
            "git branch -m <new>           # rename current branch",
        ],
        explanation=(
            "`-m` is the rename flag. If you've already pushed the old "
            "name to a remote, you'll need to push the new name and "
            "delete the old one separately."
        ),
        source="git-scm.com/docs/git-branch#Documentation/git-branch.txt--m",
        related_items=["branch.delete_remote"],
    ),

    KnowledgeItem(
        item_id="branch.list",
        topic="branch", subtopic="list", intent="how-to",
        question_patterns=[
            "list branches", "show branches", "see all branches",
            "what branches exist",
        ],
        commands=[
            "git branch                  # local branches",
            "git branch -r               # remote branches",
            "git branch -a               # all (local + remote)",
            "git branch -v               # with last commit",
        ],
        source="git-scm.com/docs/git-branch",
    ),

    KnowledgeItem(
        item_id="branch.switch",
        topic="branch", subtopic="switch", intent="how-to",
        question_patterns=[
            "switch branch", "change to branch", "checkout branch",
            "go to branch",
        ],
        commands=[
            "git checkout <branch>     # classical",
            "git switch <branch>       # modern (Git 2.23+)",
        ],
        explanation=(
            "`switch` was introduced as a clearer alternative to "
            "`checkout`, which is overloaded with non-branch behaviour."
        ),
        source="git-scm.com/docs/git-switch",
    ),

    # ----- MERGE / REBASE -----

    KnowledgeItem(
        item_id="merge.basic",
        topic="merge", subtopic="basic", intent="how-to",
        question_patterns=[
            "merge branch", "merge into main",
            "combine branches",
        ],
        commands=[
            "git checkout <target>            # the branch you want to merge INTO",
            "git merge <source-branch>",
        ],
        explanation=(
            "Merges the named branch into the current branch. Creates "
            "a merge commit unless the merge is fast-forward (linear)."
        ),
        cautions=[
            "If there are conflicts, Git stops and asks you to resolve "
            "them. After resolving, `git add` the resolved files and "
            "run `git commit` to complete the merge.",
        ],
        source="git-scm.com/docs/git-merge",
        related_items=["merge.abort", "rebase.basic", "compare.merge_vs_rebase"],
    ),

    KnowledgeItem(
        item_id="merge.abort",
        topic="merge", subtopic="abort", intent="how-to",
        question_patterns=[
            "cancel merge", "abort merge", "undo merge in progress",
            "stop merge",
        ],
        commands=[
            "git merge --abort",
        ],
        explanation=(
            "Aborts an in-progress merge that has conflicts you don't "
            "want to resolve right now. Returns the working tree to "
            "its pre-merge state."
        ),
        source="git-scm.com/docs/git-merge#Documentation/git-merge.txt---abort",
        related_items=["merge.basic"],
    ),

    KnowledgeItem(
        item_id="rebase.basic",
        topic="rebase", subtopic="basic", intent="how-to",
        question_patterns=[
            "rebase branch", "rebase onto main",
            "linear history",
        ],
        commands=[
            "git checkout <feature-branch>",
            "git rebase <base-branch>",
        ],
        explanation=(
            "Replays your branch's commits on top of the named base "
            "branch, producing a linear history (no merge commit). "
            "Each commit is recreated with a new SHA."
        ),
        cautions=[
            "Don't rebase commits that have been pushed to a shared "
            "branch. Rewriting public history breaks collaborators.",
            "Conflicts may be raised per commit, requiring per-commit "
            "resolution with `git rebase --continue`.",
        ],
        source="git-scm.com/docs/git-rebase",
        related_items=["merge.basic", "compare.merge_vs_rebase", "rebase.abort"],
    ),

    KnowledgeItem(
        item_id="rebase.abort",
        topic="rebase", subtopic="abort", intent="how-to",
        question_patterns=[
            "abort rebase", "cancel rebase", "stop rebase",
        ],
        commands=[
            "git rebase --abort",
        ],
        explanation=(
            "Cancels an in-progress rebase and returns to the state "
            "before it started."
        ),
        source="git-scm.com/docs/git-rebase",
    ),

    KnowledgeItem(
        item_id="compare.merge_vs_rebase",
        topic="rebase", subtopic="compare", intent="compare",
        question_patterns=[
            "merge vs rebase", "difference between merge and rebase",
            "should I merge or rebase",
            "when to merge vs when to rebase",
        ],
        commands=[],
        explanation=(
            "MERGE preserves the history of both branches, adding a "
            "merge commit. The result shows branching context but is "
            "non-linear. Safe on shared branches.\n\n"
            "REBASE replays your commits on top of the target, "
            "producing a linear history. Cleaner log but rewrites "
            "your commits' SHAs.\n\n"
            "Convention: rebase your LOCAL branches before merging or "
            "pushing; merge into MAIN/SHARED branches without rebasing "
            "them."
        ),
        cautions=[
            "Never rebase commits that exist on a shared branch.",
            "Rebase rewrites SHAs, so any branches/tags pointing to "
            "the old commits become detached.",
        ],
        source="git-scm.com/book/en/v2/Git-Branching-Rebasing",
        related_items=["merge.basic", "rebase.basic"],
    ),

    # ----- STATUS / INSPECTION -----

    KnowledgeItem(
        item_id="status.show",
        topic="status", subtopic="show", intent="how-to",
        question_patterns=[
            "what's changed", "see changes", "what files changed",
            "show modified files",
        ],
        commands=[
            "git status                  # summary of working tree",
            "git diff                    # unstaged changes",
            "git diff --staged           # staged changes",
            "git diff HEAD               # all uncommitted changes",
        ],
        source="git-scm.com/docs/git-status",
    ),

    KnowledgeItem(
        item_id="log.history",
        topic="log", subtopic="history", intent="how-to",
        question_patterns=[
            "see commit history", "show history", "git log",
            "list commits",
        ],
        commands=[
            "git log                            # full history",
            "git log --oneline                  # one line per commit",
            "git log --graph --oneline --all    # branch graph",
            "git log -p                         # with diffs",
            "git log --since='2 weeks ago'      # filter by date",
        ],
        source="git-scm.com/docs/git-log",
    ),

    KnowledgeItem(
        item_id="diff.compare_branches",
        topic="diff", subtopic="compare", intent="how-to",
        question_patterns=[
            "compare branches", "diff between branches",
            "what's different between branches",
        ],
        commands=[
            "git diff <branch-a>..<branch-b>",
            "git log <branch-a>..<branch-b>     # commits in b not in a",
        ],
        source="git-scm.com/docs/git-diff",
    ),

    # ----- STASH -----

    KnowledgeItem(
        item_id="stash.basic",
        topic="stash", subtopic="basic", intent="how-to",
        question_patterns=[
            "stash changes", "save changes for later", "shelve work",
            "temporarily put away changes",
        ],
        commands=[
            "git stash                           # stash current changes",
            "git stash push -m 'message'         # stash with description",
            "git stash list                      # show stashes",
            "git stash pop                       # apply + drop most recent",
            "git stash apply                     # apply without dropping",
        ],
        explanation=(
            "Stash saves your uncommitted changes (both staged and "
            "unstaged) to a stack and resets the working tree. Useful "
            "when you need to switch context quickly."
        ),
        cautions=[
            "By default, stash doesn't include untracked files. Use "
            "`-u` (or `--include-untracked`) to include them.",
            "Stashes are local; they don't sync with remotes.",
        ],
        source="git-scm.com/docs/git-stash",
    ),

    # ----- REMOTE / NETWORK -----

    KnowledgeItem(
        item_id="compare.fetch_vs_pull",
        topic="remote", subtopic="compare", intent="compare",
        question_patterns=[
            "fetch vs pull", "difference between fetch and pull",
            "what does fetch do",
        ],
        commands=[],
        explanation=(
            "FETCH downloads remote changes but does NOT merge them "
            "into your working tree. Updates remote-tracking branches "
            "(like origin/main).\n\n"
            "PULL is essentially `fetch + merge` (or `fetch + rebase` "
            "if you've set `pull.rebase=true`). It updates your "
            "current branch with the remote's new commits.\n\n"
            "Use FETCH when you want to see what's on the remote before "
            "integrating; use PULL when you want to integrate "
            "immediately."
        ),
        source="git-scm.com/docs/git-fetch",
        related_items=["push.basic"],
    ),

    KnowledgeItem(
        item_id="push.basic",
        topic="remote", subtopic="push", intent="how-to",
        question_patterns=[
            "push changes", "push to remote", "send to github",
            "publish branch",
        ],
        commands=[
            "git push                                  # push current branch to its upstream",
            "git push origin <branch>                  # push to specific remote/branch",
            "git push -u origin <branch>               # set upstream on first push",
            "git push --force-with-lease               # safer than --force",
        ],
        cautions=[
            "Avoid `--force`; use `--force-with-lease` instead, which "
            "refuses if the remote has commits you haven't seen.",
            "Never force-push to a shared branch (e.g., main/master) "
            "without team coordination.",
        ],
        source="git-scm.com/docs/git-push",
    ),

    KnowledgeItem(
        item_id="pull.basic",
        topic="remote", subtopic="pull", intent="how-to",
        question_patterns=[
            "pull changes", "update from remote", "get latest",
        ],
        commands=[
            "git pull                            # default: fetch + merge",
            "git pull --rebase                   # fetch + rebase (linear history)",
        ],
        source="git-scm.com/docs/git-pull",
        related_items=["compare.fetch_vs_pull"],
    ),

    # ----- CHERRY-PICK -----

    KnowledgeItem(
        item_id="cherry_pick.basic",
        topic="cherry-pick", subtopic="basic", intent="how-to",
        question_patterns=[
            "cherry pick commit", "apply commit to another branch",
            "copy commit to another branch",
        ],
        commands=[
            "git cherry-pick <commit-sha>",
            "git cherry-pick <sha1> <sha2>             # multiple commits",
            "git cherry-pick <start>..<end>            # range",
        ],
        explanation=(
            "Applies the changes from the named commit(s) onto the "
            "current branch as new commits. Useful for backporting "
            "fixes or grafting specific changes between branches."
        ),
        cautions=[
            "Cherry-picked commits get new SHAs; the original commit "
            "is unchanged.",
            "Conflicts must be resolved per-commit if they arise.",
        ],
        source="git-scm.com/docs/git-cherry-pick",
    ),

    # ----- DETACHED HEAD / RECOVERY -----

    KnowledgeItem(
        item_id="detached_head.what_is",
        topic="head", subtopic="detached", intent="what-is",
        question_patterns=[
            "detached head", "what is detached head",
            "you are in detached head state",
        ],
        commands=[
            "git switch -                          # back to previous branch",
            "git switch -c <new-branch>            # save current state to a new branch",
        ],
        explanation=(
            "Detached HEAD means HEAD points directly at a commit "
            "rather than to a branch. Happens after `git checkout "
            "<sha>` or `git checkout <tag>`. Any commits you make in "
            "this state are not on a branch and can be lost. Either "
            "switch back to a branch or save current state to a new "
            "branch first."
        ),
        cautions=[
            "Commits made in detached HEAD aren't on any branch. If "
            "you switch away without saving them to a branch, they "
            "become unreachable (though `git reflog` can recover them).",
        ],
        source="git-scm.com/docs/git-checkout",
        related_items=["recovery.reflog"],
    ),

    KnowledgeItem(
        item_id="recovery.reflog",
        topic="recovery", subtopic="reflog", intent="how-to",
        question_patterns=[
            "lost commits", "recover deleted commit",
            "undo bad reset", "find lost work",
        ],
        commands=[
            "git reflog                            # show HEAD's history of moves",
            "git reset --hard <sha-from-reflog>    # restore to that state",
        ],
        explanation=(
            "The reflog records every move of HEAD (commits, "
            "checkouts, resets, etc.) for the last 90 days by default. "
            "Even if a commit appears 'lost' (deleted branch, hard "
            "reset, etc.), its SHA usually still exists in the reflog "
            "for recovery."
        ),
        source="git-scm.com/docs/git-reflog",
    ),

    # ----- TAGS -----

    KnowledgeItem(
        item_id="tag.create",
        topic="tag", subtopic="create", intent="how-to",
        question_patterns=[
            "create tag", "make a release tag", "tag a version",
            "push tags to remote", "push tag to remote",
            "push all tags", "push tags",
        ],
        commands=[
            'git tag v1.0.0                                  # lightweight tag',
            'git tag -a v1.0.0 -m "Release v1.0.0"           # annotated tag (recommended)',
            "git push origin v1.0.0                          # push tag to remote",
            "git push origin --tags                          # push all tags",
        ],
        explanation=(
            "Tags are named references to specific commits, typically "
            "used for releases. Annotated tags (-a) are stored as full "
            "Git objects with author/date/message; lightweight tags "
            "are just pointers."
        ),
        source="git-scm.com/docs/git-tag",
    ),

    # ----- FILE OPERATIONS -----

    KnowledgeItem(
        item_id="file.restore_old_version",
        topic="file", subtopic="restore", intent="how-to",
        question_patterns=[
            "restore file from previous commit",
            "revert single file",
            "checkout old version of file",
            "get old version of a file",
        ],
        commands=[
            "git checkout <commit-sha> -- <file>           # restore file from commit",
            "git restore --source=<sha> <file>             # modern equivalent",
        ],
        explanation=(
            "Restores a single file to its state at the named commit, "
            "leaving other files untouched. The restored file is "
            "placed in the working tree (and staged in the classical "
            "form)."
        ),
        source="git-scm.com/docs/git-restore",
        related_items=["file.unstage"],
    ),

    KnowledgeItem(
        item_id="file.unstage",
        topic="file", subtopic="unstage", intent="how-to",
        question_patterns=[
            "unstage file", "remove file from staging",
            "undo git add",
        ],
        commands=[
            "git restore --staged <file>     # modern",
            "git reset HEAD <file>           # classical",
        ],
        source="git-scm.com/docs/git-restore",
    ),

    KnowledgeItem(
        item_id="file.ignore",
        topic="file", subtopic="ignore", intent="how-to",
        question_patterns=[
            "ignore file", "gitignore", "stop tracking file",
        ],
        commands=[
            "echo '<pattern>' >> .gitignore",
            "git rm --cached <file>            # stop tracking an already-tracked file",
        ],
        explanation=(
            ".gitignore patterns prevent Git from tracking matching "
            "files. Patterns added AFTER a file is already tracked "
            "don't untrack it — you must `git rm --cached <file>` to "
            "remove it from the index."
        ),
        source="git-scm.com/docs/gitignore",
    ),

    # ----- INITIAL SETUP -----

    KnowledgeItem(
        item_id="setup.init",
        topic="setup", subtopic="init", intent="how-to",
        question_patterns=[
            "initialise repo", "start git repo", "new git repository",
            "git init",
        ],
        commands=[
            "git init                                      # new repo here",
            "git init <directory>                          # new repo at <directory>",
            "git init --initial-branch=main                # name the initial branch",
        ],
        source="git-scm.com/docs/git-init",
    ),

    KnowledgeItem(
        item_id="setup.clone",
        topic="setup", subtopic="clone", intent="how-to",
        question_patterns=[
            "clone repo", "checkout from github", "download repo",
        ],
        commands=[
            "git clone <url>",
            "git clone <url> <directory>",
            "git clone --depth 1 <url>                     # shallow clone (no history)",
        ],
        source="git-scm.com/docs/git-clone",
    ),

    KnowledgeItem(
        item_id="setup.identity",
        topic="setup", subtopic="config", intent="how-to",
        question_patterns=[
            "set name and email", "configure git",
            "set git user", "first time git setup",
        ],
        commands=[
            'git config --global user.name "Your Name"',
            'git config --global user.email "you@example.com"',
            "git config --list                              # see all settings",
        ],
        source="git-scm.com/docs/git-config",
    ),

    # ----- COMPARING -----

    KnowledgeItem(
        item_id="compare.reset_vs_revert_vs_checkout",
        topic="undo", subtopic="compare", intent="compare",
        question_patterns=[
            "reset vs revert", "difference between reset and revert",
            "reset vs checkout",
        ],
        commands=[],
        explanation=(
            "RESET moves the branch pointer to a different commit. "
            "Rewrites history (DANGEROUS on shared branches). Modes:\n"
            "  --soft: keep changes staged\n"
            "  default: keep changes unstaged\n"
            "  --hard: discard changes (destructive)\n\n"
            "REVERT creates a NEW commit that undoes a specific "
            "commit's changes. Safe on shared branches; preserves "
            "history.\n\n"
            "CHECKOUT (legacy) or RESTORE (modern) restores file "
            "content from a specific commit without moving branch "
            "pointers."
        ),
        source="git-scm.com/docs/git-reset",
        related_items=["commit.undo_last_unpushed", "commit.revert_pushed",
                        "file.restore_old_version"],
    ),

    KnowledgeItem(
        item_id="conflict.resolve",
        topic="conflict", subtopic="resolve", intent="how-to",
        question_patterns=[
            "merge conflict", "resolve conflict", "fix conflicts",
            "conflict markers",
        ],
        commands=[
            "git status                              # see which files are in conflict",
            "<edit conflicting files; remove <<<<, ====, >>>> markers>",
            "git add <resolved-files>",
            "git commit                              # if merging",
            "git rebase --continue                   # if rebasing",
        ],
        explanation=(
            "When Git can't auto-merge changes, it marks the "
            "conflicting region in each affected file with "
            "<<<<<<< / ======= / >>>>>>> markers. Edit each file to "
            "the desired final form, remove the markers, `git add` "
            "the file, and continue the merge/rebase."
        ),
        cautions=[
            "Removing the markers but not actually resolving the "
            "conflict produces a broken commit. Always inspect the "
            "result carefully.",
        ],
        source="git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging",
    ),

    KnowledgeItem(
        item_id="submodule.add",
        topic="submodule", subtopic="add", intent="how-to",
        question_patterns=[
            "add submodule", "include another repo",
            "git submodule",
        ],
        commands=[
            "git submodule add <url> <path>",
            "git submodule update --init --recursive    # fetch submodule contents",
        ],
        cautions=[
            "Submodules are powerful but add complexity to clone / "
            "pull / build workflows. Many teams prefer monorepos or "
            "package managers instead.",
        ],
        source="git-scm.com/docs/git-submodule",
    ),

    KnowledgeItem(
        item_id="bisect.find_bad_commit",
        topic="bisect", subtopic="find", intent="how-to",
        question_patterns=[
            "find which commit broke", "git bisect",
            "binary search bug",
        ],
        commands=[
            "git bisect start",
            "git bisect bad                           # current commit is broken",
            "git bisect good <known-good-sha>         # named commit is OK",
            "# Git checks out a midpoint; you test and run:",
            "git bisect good   # or `git bisect bad`",
            "git bisect reset                         # when done",
        ],
        explanation=(
            "Binary-searches commit history for the first commit "
            "introducing a bug. You mark commits as 'good' or 'bad'; "
            "Git narrows the search by halving the range each step. "
            "Finds the breaking commit in O(log N) steps."
        ),
        source="git-scm.com/docs/git-bisect",
    ),

    KnowledgeItem(
        item_id="blame.who_changed_this_line",
        topic="blame", subtopic="line", intent="how-to",
        question_patterns=[
            "who changed this line", "git blame",
            "when was this line added",
        ],
        commands=[
            "git blame <file>",
            "git blame -L <start-line>,<end-line> <file>",
            "git log -p -S 'string' -- <file>             # find commits that added/removed a string",
        ],
        source="git-scm.com/docs/git-blame",
    ),

    KnowledgeItem(
        item_id="worktree.parallel",
        topic="worktree", subtopic="create", intent="how-to",
        question_patterns=[
            "two branches at once", "parallel checkouts",
            "git worktree",
        ],
        commands=[
            "git worktree add <path> <branch>",
            "git worktree list",
            "git worktree remove <path>",
        ],
        explanation=(
            "Allows you to have multiple working trees from one repo, "
            "each on a different branch. Useful when you need to work "
            "on two branches simultaneously without committing/stashing."
        ),
        source="git-scm.com/docs/git-worktree",
    ),
]


# ----------------------------------------------------------------------
# Convenience indexes.
# ----------------------------------------------------------------------


def by_topic(topic: str) -> list[KnowledgeItem]:
    return [k for k in GIT_KB if k.topic == topic]


def by_id(item_id: str) -> KnowledgeItem | None:
    for k in GIT_KB:
        if k.item_id == item_id:
            return k
    return None


def all_topics() -> set[str]:
    return {k.topic for k in GIT_KB}


if __name__ == "__main__":
    print(f"Git knowledge base: {len(GIT_KB)} entries")
    print(f"Topics: {sorted(all_topics())}")
    print(f"Intents: {sorted({k.intent for k in GIT_KB})}")

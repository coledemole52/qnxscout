# Owner checklist: submitting qnxscout to the QNX Global Hackathon

**Deadline: December 15, 2026, 2:00 pm Eastern (Toronto) time.** Judging runs January 15–29, 2027, and winners are announced around February 4, 2027.
Hackathon: https://qnx.devpost.com/ · Rules: https://qnx.devpost.com/rules · Sponsor: BlackBerry Ltd (Waterloo, ON).

Everything below is ready except steps that need your identity, accounts, or acceptance of terms.

## 1. Publish the repository (about 10 minutes)

The rules require a **public** GitHub/GitLab/Bitbucket repository with a detectable open-source license
(Apache-2.0 is in `LICENSE`).

1. On GitHub, create an empty public repository named `qnxscout`. Leave out the README, license, and .gitignore.
2. From the `qnxscout.bundle` file you were sent:

```bash
git clone qnxscout.bundle qnxscout
```

```bash
cd qnxscout && scripts/set-owner.sh YOUR_GITHUB_USERNAME
```

```bash
git commit -am "Set repository owner" && git branch -M main
```

```bash
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/qnxscout.git && git push -u origin main
```

3. Tag a release so the GitHub Action reference `@v0.1.0` works:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

4. On the GitHub repository page, add the description "Know what breaks before you port to QNX 8.0" and the topics
   `qnx`, `porting`, `static-analysis`, `sarif`. Check that GitHub shows "Apache-2.0 license" in the About box. The rules
   require the license to be visible there.

Commits are authored as `pontefractcole <pontefractcole@gmail.com>`. To use a different name, run
`git config user.name "Your Name"` before committing, or rewrite the history before pushing.

## 2. Register for the hackathon

Join at https://qnx.devpost.com/ with your Devpost account. You must be 18+, and Ontario residents are eligible.

## 3. Video (required, under 3 minutes, public on YouTube)

* A ready-made captioned video is included: `qnxscout-demo.mp4` (2:34, 1080p, no audio, no third-party music).
  Its end card points viewers to the description, so you can upload it as is. Put your repository URL in the
  YouTube description.
* **Strongly recommended:** record the voice-over from `docs/submission/VIDEO_SCRIPT.md` over the video (any phone or laptop
  recorder plus a basic editor). Narrated entries score better.
* Upload to YouTube as **Public**, with title "qnxscout - Know what breaks before you port to QNX 8.0".

## 4. Optional but valuable: verify on real QNX (1–2 hours)

This turns "predicted" into "demonstrated" for the *Technological Implementation* criterion.

1. Get a free non-commercial license through QNX Everywhere: https://qnx.software/en/developers/get-started/qnx-everywhere
2. Install QNX SDP 8.0 and run `source ~/qnx800/qnxsdp-env.sh`, then:
   * `qnxscout scan tmux-3.7c.tar.gz --sdp "$QNX_TARGET"` should show findings confirmed against your SDP.
   * If any finding is contradicted (downgraded to `info`), tell your assistant and it can be fixed before submitting.
3. If you set up the QNX Developer Desktop (QEMU or Raspberry Pi 5), run `python3 -m pip install .` and
   `qnxscout scan` **on the QNX target**. qnxscout is pure Python, so it should run there too. Record 10–15 seconds of it,
   or of the codelab's `abuild -r -c -K` for tmux, and add the clip to the video at 2:12.

## 5. Fill in the Devpost submission

Open https://qnx.devpost.com/ → "Enter a Submission" and copy from `docs/submission/DEVPOST.md`:

| Devpost field | Value |
|---|---|
| Project name | qnxscout |
| Elevator pitch | from DEVPOST.md |
| About the project | the "About the project" section |
| Built with | python, c, c++, cmake, meson, sarif, github-actions, qnx |
| Try it out links | your repository URL |
| Video demo link | your YouTube URL |
| Category | **Developer Tooling & Host Tools** |
| Best Codelab / Tutorial URL | `https://github.com/YOUR_GITHUB_USERNAME/qnxscout/blob/main/docs/codelab/qnxscout-port-readiness.md` |
| Evidence of QNX use | "Evidence of QNX use" section |
| Build and run instructions | "Build and run instructions" section |

Accept the terms and submit. You can edit the draft until the deadline.

## 6. Extra reach (optional, after submitting)

* Open a pull request adding `docs/codelab/qnxscout-port-readiness.md` to https://github.com/qnx/codelabs
  (their format is already matched). That is good visibility with the judges, who are QNX staff.
* Share the project in the QNX Discord (linked from the hackathon Resources page), especially the porting frontier
  list, which is directly useful to QNX's porting team.
* Community Choice prize: share the Devpost project link once public voting opens.

## 7. If you win

Devpost will contact you. As a Canadian resident you will likely be asked for a W-8BEN form. Prizes are paid in USD, and you
report them as income in Canada.

## What is realistically on the table

| Prize | Amount | How qnxscout competes |
|---|---|---|
| Best of Developer Tooling & Host Tools | US$4,000 | Primary category |
| Developer Tooling & Host Tools runner-up | US$2,000 | Primary category |
| Grand Prize (any category) | US$10,000 | Possible for a standout entry |
| Best Codelab / Tutorial | US$3,500 | The codelab is a separate bonus entry |
| Honorable Mention (3) | US$1,000 each | Fallback |

These are judged prizes, so nothing is guaranteed. One submission can win a category prize and a bonus prize.

"""Content Quality Engine — judges the writing itself, regardless of any JD.

Analyzes resume bullets: action verbs, quantification, passive voice, tense
consistency, clichés, bullet length, redundancy, and computes the two headline
metrics (quantified-bullet % and achievement/duty ratio).

Error contract: never raises — every check degrades to an empty result.
"""
from __future__ import annotations

import re
from collections import Counter

from app.models.schemas import ContentScore, Finding

# ── Curated lists ───────────────────────────────────────────────────────────────

STRONG_VERBS = {
    "accelerated", "achieved", "architected", "automated", "boosted", "built",
    "championed", "cut", "decreased", "delivered", "designed", "developed",
    "doubled", "drove", "engineered", "expanded", "generated", "grew",
    "implemented", "improved", "increased", "initiated", "launched", "led",
    "mentored", "optimized", "orchestrated", "overhauled", "pioneered",
    "reduced", "scaled", "shipped", "slashed", "spearheaded", "streamlined",
    "strengthened", "transformed", "tripled", "won",
}

WEAK_STARTERS = {
    "responsible for", "responsible", "worked on", "helped with", "helped",
    "assisted with", "assisted", "duties included", "duties", "involved in",
    "participated in", "tasked with", "handled", "was involved", "was responsible",
    "took part in", "contributed to", "supported",
}

# Legacy PASSIVE_HINTS kept as fallback when spaCy is unavailable.
PASSIVE_HINTS = [
    " was ", " were ", " been ", " is ", " are ", " being ",
    " is built ", " was built ", " were built ", " was developed ",
    " was designed ", " is used ", " was used ", " were used ",
    " was responsible for ",
]

CLICHES = [
    "team player", "hard worker", "hard-working", "go-getter", "go getter",
    "synergy", "results-driven", "results oriented", "think outside the box",
    "detail-oriented", "detail oriented", "self-starter", "self starter",
    "dynamic", "motivated", "passionate about", "proven track record",
    "fast-paced", "good communication skills", "excellent communication skills",
]

_FIRST_PERSON_START = re.compile(r"^\s*(i|my|me|we|our)\b", re.IGNORECASE)
_ARTICLES_START = re.compile(r"^\s*(the|a|an)\b", re.IGNORECASE)

_SPACE = re.compile(r"\s+")

class ContentChecker:
    """Runs all content checks over a list of bullet strings.

    The rest of the pipeline can be pointed at this class directly
    (pure-logic, easily unit-tested) while the analyzer module below
    provides the text-splitting helpers used by the API layer.
    """

    def __init__(self, bullets: list[str], current_role_index: int | None = None):
        self.bullets = [b for b in bullets if b and b.strip()]
        # Index of the bullet where the current role begins — bullets at or
        # after this index are expected to use present tense.
        self.current_role_index = current_role_index if current_role_index is not None else len(self.bullets) - 1

    # ── per-bullet classification ────────────────────────────────────────────

    @staticmethod
    def _weak_start(bullet: str) -> str | None:
        lowered = " " + bullet.lower().strip() + " "
        for phrase in WEAK_STARTERS:
            if phrase in lowered[:40]:
                return phrase
        return None

    @staticmethod
    def _first_word(bullet: str) -> str:
        match = re.match(r"[A-Za-z']+", bullet.strip())
        return match.group(0).lower() if match else ""

    @classmethod
    def _verb_family(cls, verb: str) -> str:
        """Groups a strong verb into one of a few high-level families so the
        weak-verb suggestion is always a strong verb from the same semantic
        area instead of a random pick."""
        verb = verb.lower()
        if any(part in verb for part in ("build", "develop", "design", "architect", "engineer", "implement", "launch", "ship", "create", "write")):
            return "creating"
        if any(part in verb for part in ("lead", "mentor", "manage", "coach", "spearhead", "champion", "drive", "direct", "oversee")):
            return "leading"
        if any(part in verb for part in ("improve", "optimize", "streamline", "enhance", "accelerate", "boost", "scale", "refactor", "automate")):
            return "improving"
        if any(part in verb for part in ("reduce", "cut", "save", "decrease", "eliminate", "slash", "lower")):
            return "reducing"
        if any(part in verb for part in ("achieve", "deliver", "generate", "increase", "grow", "win", "secure", "close")):
            return "delivering"
        if any(part in verb for part in ("analyze", "research", "evaluate", "test", "measure", "forecast", "model")):
            return "analyzing"
        return "general"

    _FAMILY_VERBS: dict[str, str] = {
        "creating": "built",
        "leading": "led",
        "improving": "improved",
        "reducing": "reduced",
        "delivering": "delivered",
        "analyzing": "analyzed",
        "general": "achieved",
    }

    _STRONG_BY_FAMILY: dict[str, list[str]] = {
        "creating": ["built", "engineered", "designed", "implemented", "launched"],
        "leading": ["led", "spearheaded", "directed", "mentored"],
        "improving": ["improved", "optimized", "streamlined", "automated"],
        "reducing": ["reduced", "cut", "eliminated", "slashed"],
        "delivering": ["delivered", "generated", "increased", "won"],
        "analyzing": ["analyzed", "researched", "evaluated", "measured"],
        "general": ["achieved", "drove", "transformed"],
    }

    # ── checks ───────────────────────────────────────────────────────────────

    def weak_verb_findings(self, nlp=None) -> list[Finding]:
        """Detects weak-verb bullet openers. When spaCy is available, uses
        token.lemma_ for matching so 'architecting', 'architected', 'architects'
        all correctly resolve against the curated STRONG_VERBS set."""
        findings: list[Finding] = []
        for idx, bullet in enumerate(self.bullets, start=1):
            weak = self._weak_start(bullet)
            if not weak:
                continue
            # If spaCy is available, check if the first word is actually a
            # strong verb by lemma (catches inflected forms like 'architecting')
            if nlp is not None:
                doc = nlp(bullet)
                first_lemma_is_strong = False
                for tok in doc:
                    if tok.is_space or tok.is_punct:
                        continue
                    first_lemma_is_strong = tok.lemma_.lower() in STRONG_VERBS
                    break  # Only check the first meaningful token
                if first_lemma_is_strong:
                    continue  # Skip — this is actually a strong verb in inflected form
            first = self._first_word(bullet)
            family = self._weak_family(weak, first)
            suggestion = self._FAVORITE_FAMILY_VERBS.get(family) or self._STRONG_BY_FAMILY[family][0]
            # If the weak phrase starts with a later word, use the first noun
            # after it as a hint for the suggestion.
            after = bullet.strip()
            for phrase in sorted(WEAK_STARTERS, key=len, reverse=True):
                if after.lower().startswith(phrase):
                    after = after[len(phrase):].strip()
                    break
            example_before = f"Responsible for {after}" if after else bullet.strip()
            example_after = f"{suggestion.capitalize()} {after}" if after else bullet.strip()
            findings.append(Finding(
                category="content",
                severity="minor",
                section=f"experience bullet {idx}",
                message=f"Bullet {idx} starts with a weak phrase ('{weak}').",
                why_it_matters="Weak openings like 'Responsible for' or 'Worked on' describe duties, not impact. Recruiters and ATS keyword systems respond far better to action verbs that convey ownership.",
                fix_suggestion=f"Replace '{weak}' with a strong action verb (e.g. '{suggestion}').",
                example_before=example_before,
                example_after=example_after,
            ))
        return findings

    @staticmethod
    def _weak_family(weak: str, first_word: str) -> str:
        if any(part in weak for part in ("responsible", "duties", "tasked")):
            return "delivering"
        if "work" in weak:
            return "creating"
        if any(part in weak for part in ("help", "assist", "support", "participat", "involv", "contribute")):
            return "leading"
        return "general"

    _FAVORITE_FAMILY_VERBS = {
        "delivering": "delivered",
        "creating": "built",
        "leading": "led",
        "general": "achieved",
    }

    def quantification_findings(self) -> tuple[list[Finding], float]:
        """Returns (findings, quantified_bullet_pct)."""
        quantified: list[int] = []
        for idx, bullet in enumerate(self.bullets, start=1):
            if _QUANT_RE.search(bullet):
                quantified.append(idx)
        pct = round(100.0 * len(quantified) / len(self.bullets), 1) if self.bullets else 0.0
        unquantified = [idx for idx in range(1, len(self.bullets) + 1) if idx not in quantified]
        findings: list[Finding] = []
        for idx in unquantified:
            bullet = self.bullets[idx - 1]
            findings.append(Finding(
                category="content",
                severity="minor",
                section=f"experience bullet {idx}",
                message=f"Bullet {idx} has no quantified outcome or measurable result.",
                why_it_matters="Quantified bullets (numbers, %, $, time saved) are the single strongest signal of impact. Unquantified bullets read as duties rather than achievements.",
                fix_suggestion="Add a number, percentage, amount, or time saving to this bullet (e.g. 'reduced load time by 40%').",
                example_before=bullet,
                example_after=f"{bullet} (e.g. add '— serving 10K users' or 'reducing turnaround by 3 days')",
            ))
        return findings, pct

    def passive_voice_findings(self, nlp=None) -> list[Finding]:
        """Detects passive voice using spaCy dependency parse when available,
        falls back to substring heuristics when spaCy is unavailable."""
        findings: list[Finding] = []
        for idx, bullet in enumerate(self.bullets, start=1):
            is_passive = False
            if nlp is not None:
                doc = nlp(bullet)
                is_passive = any(tok.dep_ in ("auxpass", "nsubjpass") for tok in doc)
            else:
                lowered = " " + bullet.lower() + " "
                is_passive = any(hint in lowered for hint in PASSIVE_HINTS)

            if is_passive:
                findings.append(Finding(
                    category="content",
                    severity="info",
                    section=f"experience bullet {idx}",
                    message=f"Bullet {idx} uses passive voice.",
                    why_it_matters="Passive voice hides who did the work. Active, first-word verbs are scannable and sound more confident.",
                    fix_suggestion="Rewrite with the doer first and an active verb (e.g. 'Improved X by doing Y').",
                    example_before=bullet,
                    example_after="Start with an action verb: 'Delivered…', 'Built…', 'Reduced…'",
                ))
        return findings

    def tense_findings(self, nlp=None) -> list[Finding]:
        """Detects tense issues using spaCy morphological features when available
        (Tense=Past/Pres on VERB tokens), falls back to regex word lists."""
        findings: list[Finding] = []
        if len(self.bullets) < 1:
            return findings
        for idx, bullet in enumerate(self.bullets, start=1):
            if nlp is not None:
                # Use spaCy morphology for tense detection
                doc = nlp(bullet)
                has_past = False
                has_present = False
                for tok in doc:
                    if tok.pos_ == "VERB" and "Tense" in tok.morph:
                        tense_vals = tok.morph.get("Tense")
                        if "Past" in tense_vals:
                            has_past = True
                        if "Pres" in tense_vals:
                            has_present = True

                if idx - 1 >= self.current_role_index:
                    if has_past and not has_present:
                        findings.append(Finding(
                            category="content",
                            severity="info",
                            section=f"experience bullet {idx}",
                            message=f"Bullet {idx} may use past tense in the current role.",
                            why_it_matters="Current-role bullets should be present tense ('Leading', 'Building') while past roles use past tense ('Led', 'Built').",
                            fix_suggestion="If this is your current role, use present tense.",
                            example_before=bullet,
                            example_after="Present tense version for a current role.",
                        ))
                else:
                    if has_past and has_present:
                        findings.append(Finding(
                            category="content",
                            severity="minor",
                            section=f"experience bullet {idx}",
                            message=f"Bullet {idx} mixes present and past tense.",
                            why_it_matters="Mixed tense within one past-role bullet makes the timeline unclear.",
                            fix_suggestion="Use past tense consistently for past roles.",
                            example_before=bullet,
                            example_after="Past-tense version with all verbs in past tense.",
                        ))
            else:
                # Fallback: regex keyword lists
                lowered = bullet.lower()
                if idx - 1 >= self.current_role_index:
                    if _PAST_TENSE.search(lowered):
                        findings.append(Finding(
                            category="content",
                            severity="info",
                            section=f"experience bullet {idx}",
                            message=f"Bullet {idx} may use past tense in the current role.",
                            why_it_matters="Current-role bullets should be present tense ('Leading', 'Building') while past roles use past tense ('Led', 'Built').",
                            fix_suggestion="If this is your current role, use present tense.",
                            example_before=bullet,
                            example_after="Present tense version for a current role.",
                        ))
                elif _PRESENT_TENSE.search(lowered) and _PAST_TENSE.search(lowered):
                    findings.append(Finding(
                        category="content",
                        severity="minor",
                        section=f"experience bullet {idx}",
                        message=f"Bullet {idx} mixes present and past tense.",
                        why_it_matters="Mixed tense within one past-role bullet makes the timeline unclear.",
                        fix_suggestion="Use past tense consistently for past roles.",
                        example_before=bullet,
                        example_after="Past-tense version with all verbs in past tense.",
                    ))
        return findings

    def cliche_findings(self) -> list[Finding]:
        findings: list[Finding] = []
        for idx, bullet in enumerate(self.bullets, start=1):
            lowered = bullet.lower()
            for cliche in CLICHES:
                if cliche in lowered:
                    findings.append(Finding(
                        category="content",
                        severity="info",
                        section=f"experience bullet {idx}",
                        message=f"Cliché/buzzword detected: '{cliche}'. Show, don't tell.",
                        why_it_matters="Unsupported buzzwords are discounted by recruiters and dilute the impact of real achievements.",
                        fix_suggestion="Replace the buzzword with a concrete example or quantified outcome.",
                        example_before=bullet,
                        example_after="Concrete achievement that demonstrates the quality without the buzzword.",
                    ))
                    break
        return findings

    def style_findings(self) -> list[Finding]:
        findings: list[Finding] = []
        for idx, bullet in enumerate(self.bullets, start=1):
            if _FIRST_PERSON_START.match(bullet) or _ARTICLES_START.match(bullet):
                findings.append(Finding(
                    category="content",
                    severity="info",
                    section=f"experience bullet {idx}",
                    message=f"Bullet {idx} starts with a first-person pronoun or article.",
                    why_it_matters="Resumes conventionally drop 'I', 'my', 'the' — bullets should start directly with an action verb.",
                    fix_suggestion="Remove the pronoun/article and start with an action verb.",
                    example_before=bullet,
                    example_after=re.sub(r"^\s*(I|my|me|we|our|the|a|an)\s+", "", bullet, flags=re.IGNORECASE).strip(),
                ))
        return findings

    def bullet_length_findings(self) -> list[Finding]:
        """Flags bullets > ~2 lines (~160 chars) as too long; < 30 chars as too sparse."""
        findings: list[Finding] = []
        for idx, bullet in enumerate(self.bullets, start=1):
            length = len(bullet)
            if length > 160:
                findings.append(Finding(
                    category="content",
                    severity="minor",
                    section=f"experience bullet {idx}",
                    message=f"Bullet {idx} is {length} characters — likely too long to scan.",
                    why_it_matters="Long, dense bullets are skipped by both ATS keyword systems and recruiters skimming at 6 seconds.",
                    fix_suggestion="Split it into two focused bullets, each with its own verb and outcome.",
                    example_before=bullet,
                    example_after="Two shorter bullets, each with an action verb and a measurable result.",
                ))
            elif length < 30:
                findings.append(Finding(
                    category="content",
                    severity="info",
                    section=f"experience bullet {idx}",
                    message=f"Bullet {idx} is only {length} characters — may be too vague to carry meaning.",
                    why_it_matters="Very short bullets usually lack the context a recruiter needs to understand scope and impact.",
                    fix_suggestion="Expand with the 'what, how, and result' formula.",
                    example_before=bullet,
                    example_after="Expanded bullet with what was done, how, and the result.",
                ))
        return findings

    def redundancy_findings(self) -> list[Finding]:
        """Flags verbs used to open 3+ bullets and near-duplicate bullets."""
        findings: list[Finding] = []
        first_words = [self._first_word(b) for b in self.bullets]
        counts = Counter(word for word in first_words if word)
        for word, count in counts.items():
            if count >= 3:
                findings.append(Finding(
                    category="content",
                    severity="minor",
                    section="experience",
                    message=f"The verb '{word}' opens {count} bullets.",
                    why_it_matters="Repeating the same opener dulls the impact and signals a limited vocabulary — every bullet should read distinctly.",
                    fix_suggestion=f"Vary the openers. Replace {count - 1} of them with synonyms from the same semantic family.",
                    example_before="Led… / Led… / Led…",
                    example_after="Led… / Directed… / Mentored…",
                ))
        # Near-duplicate bullets (high word overlap on short bullets)
        for i in range(len(self.bullets)):
            for j in range(i + 1, len(self.bullets)):
                if abs(len(self.bullets[i]) - len(self.bullets[j])) > 20:
                    continue
                set_i = set(re.findall(r"[a-z]+", self.bullets[i].lower()))
                set_j = set(re.findall(r"[a-z]+", self.bullets[j].lower()))
                if not set_i or not set_j:
                    continue
                overlap = len(set_i & set_j) / min(len(set_i), len(set_j))
                if overlap > 0.75:
                    findings.append(Finding(
                        category="content",
                        severity="info",
                        section="experience",
                        message=f"Bullets {i + 1} and {j + 1} look near-duplicate.",
                        why_it_matters="Repeated achievements waste space that could hold a new, distinct result.",
                        fix_suggestion="Merge them into one bullet or differentiate the second with a different outcome.",
                        example_before=f"Bullet {i + 1}: {self.bullets[i]}\nBullet {j + 1}: {self.bullets[j]}",
                        example_after="A single, combined bullet with a richer outcome.",
                    ))
                    break
        return findings

    def achievement_duty_ratio(self) -> float:
        """Ratio of achievement bullets to duty bullets (0.0–1.0).

        Achievement = quantified outcome, comparative outcome word, or a
        strong output verb; duty = task-focused verb with no outcome signal.
        """
        if not self.bullets:
            return 0.0
        achievements = 0
        for bullet in self.bullets:
            if _QUANT_RE.search(bullet):
                achievements += 1
                continue
            lowered = bullet.lower()
            if any(word in lowered for word in ("successfully", "result", "outcome", "improve", "increase", "reduce", "deliver", "launch", "build", "lead", "win", "grow")):
                achievements += 1
        return round(achievements / len(self.bullets), 2)

    def _run_all(self) -> dict[str, list[Finding]]:
        weak_verbs = self.weak_verb_findings()
        quant_findings, _pct = self.quantification_findings()
        return {
            "weak_verbs": weak_verbs,
            "quantification": quant_findings,
            "passive": self.passive_voice_findings(),
            "tense": self.tense_findings(),
            "cliche": self.cliche_findings(),
            "style": self.style_findings(),
            "length": self.bullet_length_findings(),
            "redundancy": self.redundancy_findings(),
        }

    def analyze(self) -> ContentScore:
        """Runs every check and produces the ContentScore with all findings."""
        weak_verbs = self.weak_verb_findings()
        quant_findings, pct = self.quantification_findings()
        all_findings = (
            weak_verbs
            + quant_findings
            + self.passive_voice_findings()
            + self.tense_findings()
            + self.cliche_findings()
            + self.style_findings()
            + self.bullet_length_findings()
            + self.redundancy_findings()
        )
        ratio = self.achievement_duty_ratio()

        # Score: start at 100, subtract weighted penalties.
        critical = sum(1 for f in all_findings if f.severity == "critical")
        major = sum(1 for f in all_findings if f.severity == "major")
        minor = sum(1 for f in all_findings if f.severity == "minor")
        info = sum(1 for f in all_findings if f.severity == "info")
        penalty = critical * 15 + major * 10 + minor * 6 + info * 2
        # Achievements ratio is scored as a bonus/penalty component.
        ratio_penalty = round((1.0 - ratio) * 10, 1) if self.bullets else 0.0
        score = max(0.0, round(100.0 - penalty - ratio_penalty, 1))

        return ContentScore(
            score=score,
            quantified_bullet_pct=pct,
            weak_verb_count=len(weak_verbs),
            achievement_duty_ratio=ratio,
        )


_QUANT_RE = re.compile(
    r"\d+(\.\d+)?\s*(%|percent|\$|usd|k|m|billion|million|thousand|users|"
    r"requests|hours|days|weeks|months|years|customers|clients|projects|"
    r"downloads|sales|revenue|ms|gb|tb|gb/s|seats)"
    r"|(?:increase|decrease|reduce|cut|boost|grow|save|shave)\s+(?:by\s+)?\d+"
    r"|(?:top|bottom)\s*\d+"
    r"|\$\s?\d+",
    re.IGNORECASE,
)

_PAST_TENSE = re.compile(
    r"\b(led|built|developed|designed|implemented|managed|created|launched|"
    r"delivered|reduced|improved|increased|optimized|streamlined|automated|"
    r"engineered|architected|established|founded|mentored|trained|hired|"
    r"won|achieved|drove|spearheaded|transformed|scaled|coordinated)\b",
    re.IGNORECASE,
)

_PRESENT_TENSE = re.compile(
    r"\b(lead|build|develop|design|implement|manage|create|launch|deliver|"
    r"reduce|improve|increase|optimize|streamline|automate|engineer|architect|"
    r"establish|found|mentor|train|hire|win|achieve|drive|spearhead|transform|"
    r"scale|coordinate)\b",
    re.IGNORECASE,
)


def analyze_content(
    bullets: list[str],
    current_role_index: int | None = None,
    nlp=None,
) -> tuple[ContentScore, list[Finding]]:
    """Public entry point: analyze a list of resume bullets.

    Returns (ContentScore, findings) — the findings feed the unified report
    while the score carries the headline metrics.

    When `nlp` is provided (a loaded spaCy pipeline), passive voice detection
    uses dependency parsing and tense detection uses morphological features,
    replacing the regex/substring fallbacks. Falls back gracefully to regex
    when spaCy is unavailable.
    """
    checker = ContentChecker(bullets, current_role_index=current_role_index)
    findings = (
        checker.weak_verb_findings(nlp=nlp)
        + checker.quantification_findings()[0]
        + checker.passive_voice_findings(nlp=nlp)
        + checker.tense_findings(nlp=nlp)
        + checker.cliche_findings()
        + checker.style_findings()
        + checker.bullet_length_findings()
        + checker.redundancy_findings()
    )
    return checker.analyze(), findings

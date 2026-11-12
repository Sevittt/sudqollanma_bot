"""
Gamification qoidalari — Flutter ilovasi serveridagi
functions/src/gamification/rules.ts bilan bir xil boʻlishi kerak.

Bot Admin SDK orqali yozgani uchun Firestore rules uni tekshirmaydi,
shuning uchun bu qoidalar bot tomonida ham qoʻllanadi.
Firebase'ga bogʻliq emas — unit testlarda ishlatiladi.
"""

# Ilovadagi CourtRole lavozimlari. `admin` bot orqali hech qachon berilmaydi.
ALLOWED_ROLES = ("judge", "assistant", "chancellery", "archive", "ict_specialist")

QUIZ_PASS_PERCENT = 70
XP_QUIZ_PASS = 20
XP_QUIZ_PERFECT = 50

# Bitta testga bogʻlanmagan aralash/mashq testlari XP bermaydi.
PRACTICE_QUIZ_IDS = ("random_mix", "bot_quiz")

_THRESHOLDS = {
    "intermediate": 100,
    "advanced": 500,
    "specialist": 1000,
    "expert": 2000,
    "master": 5000,
}
_GATEKEEPERS = {
    "quizzes_passed_for_expert": 5,
    "quizzes_aced_for_expert": 3,
    "streak_for_master": 7,
    "sims_for_master": 3,
}

LEVEL_LABELS = {
    "levelBeginner": "Boshlangʻich",
    "levelIntermediate": "Oʻrta",
    "levelAdvanced": "Ilgʻor",
    "levelSpecialist": "Mutaxassis",
    "levelExpert": "Ekspert",
    "levelMaster": "Usta",
}

# Keyingi darajaga oʻtish uchun XP chegarasi (oxirgisida None).
_NEXT_THRESHOLD = {
    "levelBeginner": _THRESHOLDS["intermediate"],
    "levelIntermediate": _THRESHOLDS["advanced"],
    "levelAdvanced": _THRESHOLDS["specialist"],
    "levelSpecialist": _THRESHOLDS["expert"],
    "levelExpert": _THRESHOLDS["master"],
    "levelMaster": None,
}


def is_allowed_role(role) -> bool:
    return role in ALLOWED_ROLES


def to_int(value) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def counters_of(user: dict) -> dict:
    return {
        "xp": to_int(user.get("xp")),
        "quizzes_passed": to_int(user.get("quizzesPassed")),
        "quizzes_aced": to_int(user.get("totalQuizzesAced")),
        "current_streak": to_int(user.get("currentStreak")),
        "simulations_completed": to_int(user.get("simulationsCompleted")),
    }


def calculate_level(c: dict) -> str:
    """rules.ts calculateLevel bilan bir xil gatekeeper mantigʻi."""
    xp = c["xp"]
    g = _GATEKEEPERS
    if xp >= _THRESHOLDS["master"]:
        if c["simulations_completed"] >= g["sims_for_master"] and c["current_streak"] >= g["streak_for_master"]:
            return "levelMaster"
        return "levelExpert"
    if xp >= _THRESHOLDS["expert"]:
        if c["quizzes_passed"] >= g["quizzes_passed_for_expert"] and c["quizzes_aced"] >= g["quizzes_aced_for_expert"]:
            return "levelExpert"
        return "levelSpecialist"
    if xp >= _THRESHOLDS["specialist"]:
        return "levelSpecialist"
    if xp >= _THRESHOLDS["advanced"]:
        return "levelAdvanced"
    if xp >= _THRESHOLDS["intermediate"]:
        return "levelIntermediate"
    return "levelBeginner"


def quiz_action(quiz_id: str, score: int, total: int):
    """Test natijasi uchun harakat: 'quiz_aced', 'quiz_passed' yoki None (XP yoʻq)."""
    if not quiz_id or quiz_id in PRACTICE_QUIZ_IDS or total <= 0:
        return None
    if score * 100 < QUIZ_PASS_PERCENT * total:
        return None
    return "quiz_aced" if score >= total else "quiz_passed"


def quiz_points(action) -> int:
    if action == "quiz_aced":
        return XP_QUIZ_PASS + XP_QUIZ_PERFECT
    if action == "quiz_passed":
        return XP_QUIZ_PASS
    return 0


def apply_quiz_award(c: dict, action: str, points: int) -> dict:
    nxt = dict(c, xp=c["xp"] + points)
    if action in ("quiz_passed", "quiz_aced"):
        nxt["quizzes_passed"] += 1
    if action == "quiz_aced":
        nxt["quizzes_aced"] += 1
    return nxt


def best_quiz_actions(attempts) -> dict:
    """
    Test urinishlaridan har bir test uchun eng yaxshi mukofot harakati
    (profil birlashtirilganda XP shu qoidalar bilan qayta hisoblanadi).
    """
    rank = {"quiz_passed": 1, "quiz_aced": 2}
    best = {}
    for a in attempts:
        action = quiz_action(a.get("quizId"), to_int(a.get("score")), to_int(a.get("totalQuestions")))
        if action and rank[action] > rank.get(best.get(a["quizId"]), 0):
            best[a["quizId"]] = action
    return best


def quiz_dedup_key(quiz_id: str) -> str:
    """Ilova bilan bir xil kalit: bitta test — bitta mukofot."""
    return f"quiz:{quiz_id}"


def level_id(user: dict) -> str:
    """Saqlangan darajani ilova formatiga keltiradi; eski qiymatlar XP dan hisoblanadi."""
    raw = user.get("level")
    if isinstance(raw, str) and raw in LEVEL_LABELS:
        return raw
    return calculate_level(counters_of(user))


def level_label(level: str) -> str:
    return LEVEL_LABELS.get(level, LEVEL_LABELS["levelBeginner"])


def next_level_threshold(level: str):
    return _NEXT_THRESHOLD.get(level)

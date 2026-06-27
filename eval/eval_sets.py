# Eval sets — Extractor & Memory Manager
#
# These are STRUCTURED-OUTPUT eval cases (not tool calls): each case is
# input -> expected structured output, scored by comparing fields.
#
# Scoring conventions:
#   Extractor:
#     - PASS if every signal in `expect_signals` has a produced signal with
#       matching category AND value (exact). Extra signals are allowed unless
#       listed in `must_not` (over-reach guard).
#     - `must_not` lists (category, value-substring) that should NOT appear,
#       used to catch trait-inference (e.g. emitting a stable preference from
#       a single event) instead of observation.
#   Memory Manager:
#     - PASS if the produced operation set contains an op matching
#       `expect_op` on op_type, and (where given) target_item_id and value.
#       NOOP cases pass if NO non-NOOP op is produced.
#     - Categorical + exact: no LLM judge needed here.
#
# Keep `dev` for tuning; report final numbers on `heldout` (do not tune to it).

# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTOR
# input: a single operator event (the fields the extractor sees)
# ─────────────────────────────────────────────────────────────────────────────

EXTRACTOR_DEV = [
    # ── Clean / baseline cases ────────────────────────────────────────────
    {
        "id": "ext-d1",
        "tests": "modality request -> VISUAL signal",
        "event": {
            "event_type": "question", "alarm_code": "PA-2201",
            "content": "Can you show me a diagram of where valve V-4 is?",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL"}],
        "must_not": [],
    },
    {
        "id": "ext-d2",
        "tests": "independent resolution of a simple alarm -> TROUBLESHOOTING/CONFIDENT",
        "event": {
            "event_type": "alarm", "alarm_code": "FL-1106",
            "content": "Already ran the auto-cal and flow is back to 5 L/min, all good.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"}],
        "must_not": [],
    },
    {
        "id": "ext-d3",
        "tests": "fast escalation of a complex alarm -> ESCALATION/ESCALATED_FAST",
        "event": {
            "event_type": "alarm", "alarm_code": "HY-0042",
            "content": "Hydraulic fault on Press B, I'm calling maintenance now.",
            "outcome": "escalated",
        },
        "expect_signals": [{"category": "ESCALATION", "value": "ESCALATED_FAST"}],
        "must_not": [],
    },
    {
        "id": "ext-d4",
        "tests": "OVER-REACH guard: single event must not yield a stable-trait inference",
        "event": {
            "event_type": "question", "alarm_code": "PA-2201",
            "content": "Show me the steps as pictures.",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL"}],
        "must_not": [("ESCALATION", ""), ("ISSUE_CONFIDENCE", "")],
    },
    {
        "id": "ext-d5",
        "tests": "explicit text-modality request -> TEXT (distinguish from VISUAL)",
        "event": {
            "event_type": "question", "alarm_code": "RC-3301",
            "content": "Just give me the checklist as text, no pictures.",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "TEXT"}],
        "must_not": [("INSTRUCTION_MODALITY", "VISUAL")],
    },
    {
        "id": "ext-d6",
        "tests": "no behavioural signal present -> empty (don't fabricate)",
        "event": {
            "event_type": "question", "alarm_code": None,
            "content": "What time does the next shift start?",
        },
        "expect_signals": [],
        "must_not": [("INSTRUCTION_MODALITY", ""), ("ESCALATION", ""), ("ISSUE_CONFIDENCE", "")],
    },

    # ── Negation ──────────────────────────────────────────────────────────
    {
        "id": "ext-d7",
        "tests": "NEGATION: 'don't show me pictures' -> TEXT not VISUAL",
        "event": {
            "event_type": "question", "alarm_code": "PA-2201",
            "content": "Don't show me pictures this time, just tell me the steps in words.",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "TEXT"}],
        "must_not": [("INSTRUCTION_MODALITY", "VISUAL")],
    },
    {
        "id": "ext-d8",
        "tests": "NEGATION: 'stop escalating for me' -> implicit confidence signal",
        "event": {
            "event_type": "question", "alarm_code": "FL-1106",
            "content": "You keep suggesting I call maintenance for these flow alarms. I can handle them myself, stop escalating for me.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"}],
        "must_not": [("ESCALATION", "ESCALATED_FAST")],
    },

    # ── Multi-signal ──────────────────────────────────────────────────────
    {
        "id": "ext-d9",
        "tests": "MULTI-SIGNAL: visual request + independent resolution in one message",
        "event": {
            "event_type": "alarm", "alarm_code": "PA-2201",
            "content": "Pressure alarm again. Checked the diagram on the panel and vented V-4 myself, all clear now.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [
            {"category": "INSTRUCTION_MODALITY", "value": "VISUAL"},
            {"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"},
        ],
        "must_not": [],
    },
    {
        "id": "ext-d10",
        "tests": "MULTI-SIGNAL: escalation + explicit text preference",
        "event": {
            "event_type": "alarm", "alarm_code": "HY-0042",
            "content": "I'm escalating this hydraulic fault now. By the way, when you send me instructions, just text is fine, I don't need diagrams.",
            "outcome": "escalated",
        },
        "expect_signals": [
            {"category": "ESCALATION", "value": "ESCALATED_FAST"},
            {"category": "INSTRUCTION_MODALITY", "value": "TEXT"},
        ],
        "must_not": [("INSTRUCTION_MODALITY", "VISUAL")],
    },

    # ── False friends ─────────────────────────────────────────────────────
    {
        "id": "ext-d11",
        "tests": "FALSE FRIEND: mentions 'escalate' but is asking about policy, not escalating",
        "event": {
            "event_type": "question", "alarm_code": None,
            "content": "When should I escalate a hydraulic alarm? What's the policy?",
        },
        "expect_signals": [],
        "must_not": [("ESCALATION", "")],
    },
    {
        "id": "ext-d12",
        "tests": "FALSE FRIEND: mentions 'picture' but is describing what they saw, not requesting modality",
        "event": {
            "event_type": "question", "alarm_code": "FL-1105",
            "content": "I saw a picture of the sensor layout on the panel, but the readings still look wrong. What should I do?",
        },
        "expect_signals": [],
        "must_not": [("INSTRUCTION_MODALITY", "VISUAL")],
    },
    {
        "id": "ext-d13",
        "tests": "FALSE FRIEND: 'I resolved it' but outcome is actually escalated (text-outcome mismatch)",
        "event": {
            "event_type": "alarm", "alarm_code": "HY-0042",
            "content": "I think I resolved it, the press looks normal now.",
            "outcome": "escalated",
        },
        "expect_signals": [{"category": "ESCALATION", "value": "ESCALATED_FAST"}],
        "must_not": [("ISSUE_CONFIDENCE", "RESOLVED_INDEPENDENT")],
    },

    # ── Implicit modality ─────────────────────────────────────────────────
    {
        "id": "ext-d14",
        "tests": "IMPLICIT: 'walk me through it step by step' -> no strong modality signal",
        "event": {
            "event_type": "question", "alarm_code": "RC-3301",
            "content": "Can you walk me through the recipe reload step by step?",
        },
        "expect_signals": [],
        "must_not": [("INSTRUCTION_MODALITY", "VISUAL"), ("INSTRUCTION_MODALITY", "TEXT")],
    },
    {
        "id": "ext-d15",
        "tests": "IMPLICIT: 'send me a video' -> VIDEO not VISUAL",
        "event": {
            "event_type": "question", "alarm_code": "FL-1105",
            "content": "Is there a video for the calibration? Send me that instead.",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "VIDEO"}],
        "must_not": [("INSTRUCTION_MODALITY", "VISUAL"), ("INSTRUCTION_MODALITY", "TEXT")],
    },

    # ── Frustration / emotion ─────────────────────────────────────────────
    {
        "id": "ext-d16",
        "tests": "FRUSTRATION: angry but self-resolving, not escalating",
        "event": {
            "event_type": "alarm", "alarm_code": "PA-2201",
            "content": "This stupid pressure alarm again! I've already vented V-4 and reset it. Third time today.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"}],
        "must_not": [("ESCALATION", ""), ("LEARNING_NEED", "")],
    },
    {
        "id": "ext-d17",
        "tests": "FRUSTRATION: expressing doubt but resolved independently (action over self-assessment)",
        "event": {
            "event_type": "question", "alarm_code": "FL-1105",
            "content": "I'm not super confident with these sensor alarms honestly, but I think I got it this time.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"}],
        "must_not": [],
    },

    # ── Shift / temporal ──────────────────────────────────────────────────
    {
        "id": "ext-d18",
        "tests": "SHIFT: operator mentions tiredness / end of shift",
        "event": {
            "event_type": "question", "alarm_code": None,
            "content": "It's been a long night shift, I'm pretty tired. Anything I should hand over?",
            "shift": "night",
        },
        "expect_signals": [{"category": "SHIFT_PATTERN", "value": "END_OF_SHIFT_FATIGUE"}],
        "must_not": [("ESCALATION", ""), ("ISSUE_CONFIDENCE", "")],
    },
]

EXTRACTOR_HELDOUT = [
    # ── Clean / baseline ──────────────────────────────────────────────────
    {
        "id": "ext-h1",
        "tests": "modality request phrased differently -> VISUAL",
        "event": {
            "event_type": "question", "alarm_code": "FL-1105",
            "content": "Walk me through it with screenshots if you have them.",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL"}],
        "must_not": [],
    },
    {
        "id": "ext-h2",
        "tests": "over-escalation of a self-resolve alarm -> ESCALATION signal",
        "event": {
            "event_type": "alarm", "alarm_code": "FL-1106",
            "content": "Low flow alarm again, escalating to maintenance.",
            "outcome": "escalated",
        },
        "expect_signals": [{"category": "ESCALATION", "value": "ESCALATED_FAST"}],
        "must_not": [],
    },
    {
        "id": "ext-h3",
        "tests": "struggled / needed help on a complex alarm -> NEEDS_SUPPORT",
        "event": {
            "event_type": "question", "alarm_code": "HY-0043",
            "content": "I don't really know what to check here, can you help?",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "NEEDS_SUPPORT"}],
        "must_not": [],
    },

    # ── Hard heldout ──────────────────────────────────────────────────────
    {
        "id": "ext-h4",
        "tests": "NEGATION: 'I don't need help with these anymore' -> confidence",
        "event": {
            "event_type": "alarm", "alarm_code": "FL-1106",
            "content": "I don't need help with these flow alarms anymore, I've got it down.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"}],
        "must_not": [("LEARNING_NEED", "")],
    },
    {
        "id": "ext-h5",
        "tests": "FALSE FRIEND: discussing escalation retrospectively, not escalating now",
        "event": {
            "event_type": "question", "alarm_code": "HY-0043",
            "content": "Last week I escalated one of these and maintenance said I did the right thing. Should I do the same now?",
        },
        "expect_signals": [{"category": "LEARNING_NEED", "value": "SEEKING_GUIDANCE"}],
        "must_not": [("ESCALATION", "ESCALATED_FAST")],
    },
    {
        "id": "ext-h6",
        "tests": "MULTI-SIGNAL + NEGATION: resolved + explicitly rejects video modality",
        "event": {
            "event_type": "alarm", "alarm_code": "FL-1105",
            "content": "Fixed the flow sensor. Please don't send me videos next time, the text checklist is way faster.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [
            {"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"},
            {"category": "INSTRUCTION_MODALITY", "value": "TEXT"},
        ],
        "must_not": [("INSTRUCTION_MODALITY", "VIDEO"), ("INSTRUCTION_MODALITY", "VISUAL")],
    },
    {
        "id": "ext-h7",
        "tests": "AMBIGUOUS: operator asks colleague (not the assistant) for help",
        "event": {
            "event_type": "question", "alarm_code": "PA-2202",
            "content": "Hey I just asked Reo next to me and he showed me how to do it. We're good.",
            "outcome": "resolved_independently",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"}],
        "must_not": [("ESCALATION", "ESCALATED_FAST")],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# MEMORY MANAGER
# input: new signals + current active memory items
# ─────────────────────────────────────────────────────────────────────────────

MEMORY_MANAGER_DEV = [
    {
        "id": "mm-d1",
        "tests": "novel belief -> ADD",
        "signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL",
                     "observation": "asked for a diagram"}],
        "current_items": [],
        "expect_op": {"op_type": "ADD", "value": "VISUAL"},
    },
    {
        "id": "mm-d2",
        "tests": "consistent repeat -> REINFORCE (not ADD)",
        "signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL",
                     "observation": "asked for pictures again"}],
        "current_items": [
            {"id": "mem_001", "category": "INSTRUCTION_MODALITY", "value": "VISUAL",
             "text": "Prefers visual instructions", "status": "tentative", "evidence_count": 2},
        ],
        "expect_op": {"op_type": "REINFORCE", "target_item_id": "mem_001"},
    },
    {
        "id": "mm-d3",
        "tests": "contradiction (same category, different value) -> SUPERSEDE",
        "signals": [{"category": "INSTRUCTION_MODALITY", "value": "TEXT",
                     "observation": "explicitly asked for text only, no pictures"}],
        "current_items": [
            {"id": "mem_001", "category": "INSTRUCTION_MODALITY", "value": "VISUAL",
             "text": "Prefers visual instructions", "status": "established", "evidence_count": 5},
        ],
        "expect_op": {"op_type": "SUPERSEDE", "target_item_id": "mem_001", "value": "TEXT"},
    },
    {
        "id": "mm-d4",
        "tests": "noise / already covered -> NOOP (no spurious ADD)",
        "signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL",
                     "observation": "asked for a diagram"}],
        "current_items": [
            {"id": "mem_001", "category": "INSTRUCTION_MODALITY", "value": "VISUAL",
             "text": "Prefers visual instructions", "status": "confirmed", "evidence_count": 12},
        ],
        "expect_op_any_of": [
            {"op_type": "REINFORCE", "target_item_id": "mem_001"},
            {"op_type": "NOOP"},
        ],
        "must_not_op": [{"op_type": "ADD"}],
    },
    {
        "id": "mm-d5",
        "tests": "different category, novel -> ADD (don't touch unrelated item)",
        "signals": [{"category": "ESCALATION", "value": "ESCALATED_FAST",
                     "observation": "escalated a hydraulic fault immediately"}],
        "current_items": [
            {"id": "mem_001", "category": "INSTRUCTION_MODALITY", "value": "VISUAL",
             "text": "Prefers visual instructions", "status": "established", "evidence_count": 5},
        ],
        "expect_op": {"op_type": "ADD", "value": "ESCALATED_FAST"},
        "must_not_op": [{"op_type": "SUPERSEDE", "target_item_id": "mem_001"}],
    },
    {
        "id": "mm-d6",
        "tests": "confirmation response -> high-weight (promotes toward confirmed)",
        "signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL",
                     "observation": "operator confirmed: yes, keep using visuals"}],
        "current_items": [
            {"id": "mem_001", "category": "INSTRUCTION_MODALITY", "value": "VISUAL",
             "text": "Prefers visual instructions", "status": "tentative", "evidence_count": 2},
        ],
        "high_weight": True,
        "expect_op": {"op_type": "REINFORCE", "target_item_id": "mem_001"},
    },
]

MEMORY_MANAGER_HELDOUT = [
    {
        "id": "mm-h1",
        "tests": "confidence flip on an alarm (struggle after prior confidence) -> SUPERSEDE",
        "signals": [{"category": "ISSUE_CONFIDENCE", "value": "NEEDS_SUPPORT",
                     "observation": "could not resolve FL-1105, asked for help"}],
        "current_items": [
            {"id": "mem_002", "category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT",
             "text": "Confident with flow-sensor alarms", "status": "established", "evidence_count": 4},
        ],
        "expect_op": {"op_type": "SUPERSEDE", "target_item_id": "mem_002", "value": "NEEDS_SUPPORT"},
    },
    {
        "id": "mm-h2",
        "tests": "two signals, one novel one consistent -> ADD + REINFORCE (not 1:1 forced)",
        "signals": [
            {"category": "INSTRUCTION_MODALITY", "value": "VISUAL", "observation": "asked for diagram"},
            {"category": "ESCALATION", "value": "ESCALATED_FAST", "observation": "escalated complex fault"},
        ],
        "current_items": [
            {"id": "mem_001", "category": "INSTRUCTION_MODALITY", "value": "VISUAL",
             "text": "Prefers visual instructions", "status": "tentative", "evidence_count": 2},
        ],
        "expect_ops": [
            {"op_type": "REINFORCE", "target_item_id": "mem_001"},
            {"op_type": "ADD", "value": "ESCALATED_FAST"},
        ],
    },
    {
        "id": "mm-h3",
        "tests": "hallucinated-target guard: agent must not target a non-existent id",
        "signals": [{"category": "SHIFT_PATTERN", "value": "SLOWER_LATE_NIGHT",
                     "observation": "slower in last hour of night shift"}],
        "current_items": [],
        "expect_op": {"op_type": "ADD", "value": "SLOWER_LATE_NIGHT"},
        "must_not_op": [{"op_type": "REINFORCE"}, {"op_type": "SUPERSEDE"}],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# MANDARIN INPUT CASES (Singapore multilingual shopfloor)
#
# CORE PRINCIPLE: input language varies, structured output stays CANONICAL.
# A Mandarin event must still produce English-enum `value` (e.g. "VISUAL"),
# never a translated value.
# ─────────────────────────────────────────────────────────────────────────────

EXTRACTOR_ZH = [
    {
        "id": "ext-zh1",
        "tests": "Mandarin modality request -> canonical VISUAL (not translated value)",
        "event": {
            "event_type": "question", "alarm_code": "PA-2201",
            "content": "可以给我看一下阀门 V-4 的图吗？",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL"}],
        "must_not": [],
    },
    {
        "id": "ext-zh2",
        "tests": "Mandarin independent resolution -> RESOLVED_INDEPENDENT",
        "event": {
            "event_type": "alarm", "alarm_code": "FL-1106",
            "content": "我已经跑了自动校准，流量恢复正常了，没问题。",
            "outcome": "resolved_independently",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "RESOLVED_INDEPENDENT"}],
        "must_not": [],
    },
    {
        "id": "ext-zh3",
        "tests": "Mandarin escalation of complex alarm -> ESCALATED_FAST",
        "event": {
            "event_type": "alarm", "alarm_code": "HY-0042",
            "content": "B 压机液压故障，我现在马上叫维修。",
            "outcome": "escalated",
        },
        "expect_signals": [{"category": "ESCALATION", "value": "ESCALATED_FAST"}],
        "must_not": [],
    },
    {
        "id": "ext-zh4",
        "tests": "Mandarin struggle on complex alarm -> NEEDS_SUPPORT",
        "event": {
            "event_type": "question", "alarm_code": "HY-0043",
            "content": "我不太清楚这里要检查什么，可以帮我吗？",
        },
        "expect_signals": [{"category": "ISSUE_CONFIDENCE", "value": "NEEDS_SUPPORT"}],
        "must_not": [],
    },
    {
        "id": "ext-zh6",
        "tests": "code-switching (mixed EN/ZH) -> still extracts canonical VISUAL",
        "event": {
            "event_type": "question", "alarm_code": "FL-1105",
            "content": "Sensor 那个 screen 在哪里？能 show 我 diagram 吗？",
        },
        "expect_signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL"}],
        "must_not": [],
    },
]

MEMORY_MANAGER_ZH = [
    {
        "id": "mm-zh1",
        "tests": "Mandarin-derived signal -> ADD with canonical value",
        "signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL",
                     "observation": "用中文要求看图 (requested a diagram, in Mandarin)"}],
        "current_items": [],
        "expect_op": {"op_type": "ADD", "value": "VISUAL"},
    },
    {
        "id": "mm-zh3",
        "tests": "consistency across languages: ZH 'VISUAL' signal REINFORCEs an EN-derived item",
        "signals": [{"category": "INSTRUCTION_MODALITY", "value": "VISUAL",
                     "observation": "用中文再次要求看图 (asked for a diagram again, in Mandarin)"}],
        "current_items": [
            {"id": "mem_001", "category": "INSTRUCTION_MODALITY", "value": "VISUAL",
             "text": "Prefers visual instructions", "status": "tentative", "evidence_count": 2},
        ],
        "expect_op": {"op_type": "REINFORCE", "target_item_id": "mem_001"},
    },
]
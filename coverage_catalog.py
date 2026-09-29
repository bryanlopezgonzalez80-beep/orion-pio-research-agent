from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoverageTopic:
    domain: str
    query: str
    biomedical: bool = False
    technology: bool = False
    priority: int = 2


# Broad, overlapping vocabulary is intentional. Different scholarly indexes use
# different terminology, and overlap improves recall while DOI/title
# deduplication controls duplication.
COVERAGE_TOPICS: tuple[CoverageTopic, ...] = (
    # Core I-O / work psychology
    CoverageTopic("Core I-O", "industrial organizational psychology", priority=1),
    CoverageTopic("Core I-O", "industrial and organizational psychology", priority=1),
    CoverageTopic("Core I-O", "organizational psychology", priority=1),
    CoverageTopic("Core I-O", "occupational psychology", priority=1),
    CoverageTopic("Core I-O", "work psychology", priority=1),
    CoverageTopic("Core I-O", "personnel psychology", priority=1),
    CoverageTopic("Core I-O", "organizational behavior", priority=1),
    CoverageTopic("Core I-O", "human resource management", priority=1),

    # Leadership
    CoverageTopic("Leadership", "leadership effectiveness", priority=1),
    CoverageTopic("Leadership", "transformational leadership"),
    CoverageTopic("Leadership", "transactional leadership"),
    CoverageTopic("Leadership", "servant leadership"),
    CoverageTopic("Leadership", "ethical leadership"),
    CoverageTopic("Leadership", "authentic leadership"),
    CoverageTopic("Leadership", "shared leadership"),
    CoverageTopic("Leadership", "leader member exchange"),
    CoverageTopic("Leadership", "leadership development"),
    CoverageTopic("Leadership", "manager coaching"),
    CoverageTopic("Leadership", "destructive leadership"),
    CoverageTopic("Leadership", "leadership derailment"),

    # Organizational development and change
    CoverageTopic("OD & Change", "organizational development", priority=1),
    CoverageTopic("OD & Change", "organizational change", priority=1),
    CoverageTopic("OD & Change", "change readiness"),
    CoverageTopic("OD & Change", "resistance to change"),
    CoverageTopic("OD & Change", "organization development intervention"),
    CoverageTopic("OD & Change", "organizational transformation"),
    CoverageTopic("OD & Change", "change management workplace"),
    CoverageTopic("OD & Change", "organizational learning"),
    CoverageTopic("OD & Change", "learning organization"),
    CoverageTopic("OD & Change", "organizational innovation"),

    # Culture, climate, justice, trust
    CoverageTopic("Culture & Climate", "organizational culture", priority=1),
    CoverageTopic("Culture & Climate", "organizational climate", priority=1),
    CoverageTopic("Culture & Climate", "psychological climate workplace"),
    CoverageTopic("Culture & Climate", "organizational justice"),
    CoverageTopic("Culture & Climate", "procedural justice workplace"),
    CoverageTopic("Culture & Climate", "organizational trust"),
    CoverageTopic("Culture & Climate", "employee voice"),
    CoverageTopic("Culture & Climate", "speak up behavior workplace"),
    CoverageTopic("Culture & Climate", "ethical climate organization"),
    CoverageTopic("Culture & Climate", "innovation climate workplace"),

    # Teams
    CoverageTopic("Teams", "team effectiveness", priority=1),
    CoverageTopic("Teams", "team performance workplace"),
    CoverageTopic("Teams", "psychological safety workplace", priority=1),
    CoverageTopic("Teams", "team cohesion"),
    CoverageTopic("Teams", "team conflict"),
    CoverageTopic("Teams", "team diversity performance"),
    CoverageTopic("Teams", "virtual teams"),
    CoverageTopic("Teams", "team leadership"),
    CoverageTopic("Teams", "team learning"),
    CoverageTopic("Teams", "collaboration workplace"),
    CoverageTopic("Teams", "knowledge sharing workplace"),

    # Talent, staffing, assessment
    CoverageTopic("Talent & Selection", "employee selection assessment", priority=1),
    CoverageTopic("Talent & Selection", "personnel selection"),
    CoverageTopic("Talent & Selection", "structured employment interview"),
    CoverageTopic("Talent & Selection", "assessment center employee selection"),
    CoverageTopic("Talent & Selection", "cognitive ability job performance"),
    CoverageTopic("Talent & Selection", "personality job performance"),
    CoverageTopic("Talent & Selection", "competency modeling"),
    CoverageTopic("Talent & Selection", "talent management", priority=1),
    CoverageTopic("Talent & Selection", "succession planning"),
    CoverageTopic("Talent & Selection", "employee retention"),
    CoverageTopic("Talent & Selection", "employee turnover"),
    CoverageTopic("Talent & Selection", "onboarding employee"),

    # Performance and motivation
    CoverageTopic("Performance & Motivation", "job performance", priority=1),
    CoverageTopic("Performance & Motivation", "performance management", priority=1),
    CoverageTopic("Performance & Motivation", "performance appraisal"),
    CoverageTopic("Performance & Motivation", "goal setting workplace"),
    CoverageTopic("Performance & Motivation", "work motivation"),
    CoverageTopic("Performance & Motivation", "self determination work"),
    CoverageTopic("Performance & Motivation", "job satisfaction"),
    CoverageTopic("Performance & Motivation", "organizational commitment"),
    CoverageTopic("Performance & Motivation", "employee engagement", priority=1),
    CoverageTopic("Performance & Motivation", "work engagement"),

    # Training, learning, careers
    CoverageTopic("Learning & Careers", "training and development workplace", priority=1),
    CoverageTopic("Learning & Careers", "training transfer", priority=1),
    CoverageTopic("Learning & Careers", "learning transfer workplace"),
    CoverageTopic("Learning & Careers", "employee development"),
    CoverageTopic("Learning & Careers", "leadership training"),
    CoverageTopic("Learning & Careers", "coaching workplace"),
    CoverageTopic("Learning & Careers", "mentoring workplace"),
    CoverageTopic("Learning & Careers", "career development"),
    CoverageTopic("Learning & Careers", "career adaptability"),
    CoverageTopic("Learning & Careers", "continuous learning workplace"),

    # Wellbeing and work design
    CoverageTopic("Wellbeing & Work Design", "workplace wellbeing", biomedical=True, priority=1),
    CoverageTopic("Wellbeing & Work Design", "employee burnout", biomedical=True, priority=1),
    CoverageTopic("Wellbeing & Work Design", "occupational stress", biomedical=True, priority=1),
    CoverageTopic("Wellbeing & Work Design", "work life balance", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "job demands resources", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "work design", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "meaningful work", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "employee resilience", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "workplace incivility", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "workplace bullying", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "occupational fatigue", biomedical=True),
    CoverageTopic("Wellbeing & Work Design", "psychosocial safety climate", biomedical=True),

    # Diversity, inclusion, ethics
    CoverageTopic("DEI & Ethics", "diversity inclusion workplace"),
    CoverageTopic("DEI & Ethics", "belonging workplace"),
    CoverageTopic("DEI & Ethics", "workplace discrimination"),
    CoverageTopic("DEI & Ethics", "gender bias workplace"),
    CoverageTopic("DEI & Ethics", "racial bias workplace"),
    CoverageTopic("DEI & Ethics", "age discrimination workplace"),
    CoverageTopic("DEI & Ethics", "disability inclusion workplace"),
    CoverageTopic("DEI & Ethics", "sexual harassment workplace"),
    CoverageTopic("DEI & Ethics", "employee ethics behavior"),
    CoverageTopic("DEI & Ethics", "corporate social responsibility employees"),

    # Technology / future of work
    CoverageTopic("Technology & Future of Work", "artificial intelligence human resources workplace", technology=True, priority=1),
    CoverageTopic("Technology & Future of Work", "AI hiring employee selection", technology=True),
    CoverageTopic("Technology & Future of Work", "people analytics", technology=True),
    CoverageTopic("Technology & Future of Work", "HR analytics", technology=True),
    CoverageTopic("Technology & Future of Work", "algorithmic management", technology=True),
    CoverageTopic("Technology & Future of Work", "employee monitoring technology", technology=True),
    CoverageTopic("Technology & Future of Work", "human AI collaboration workplace", technology=True),
    CoverageTopic("Technology & Future of Work", "automation jobs workplace", technology=True),
    CoverageTopic("Technology & Future of Work", "digital transformation employees", technology=True),
    CoverageTopic("Technology & Future of Work", "future of work", technology=True),

    # Work arrangements
    CoverageTopic("Work Arrangements", "remote work employees"),
    CoverageTopic("Work Arrangements", "hybrid work employees"),
    CoverageTopic("Work Arrangements", "flexible work arrangements"),
    CoverageTopic("Work Arrangements", "telework employee outcomes"),
    CoverageTopic("Work Arrangements", "gig work psychology"),
    CoverageTopic("Work Arrangements", "shift work employee outcomes", biomedical=True),
    CoverageTopic("Work Arrangements", "four day workweek employees"),
    CoverageTopic("Work Arrangements", "return to office employees"),

    # Safety / human factors
    CoverageTopic("Safety & Human Factors", "occupational safety behavior", biomedical=True),
    CoverageTopic("Safety & Human Factors", "safety climate workplace", biomedical=True),
    CoverageTopic("Safety & Human Factors", "human factors work performance"),
    CoverageTopic("Safety & Human Factors", "ergonomics employee performance", biomedical=True),
    CoverageTopic("Safety & Human Factors", "human error workplace"),
    CoverageTopic("Safety & Human Factors", "safety leadership workplace", biomedical=True),

    # Puerto Rico / Latin America / Spanish-language discovery
    CoverageTopic("Puerto Rico & LATAM", "industrial organizational psychology Puerto Rico", priority=1),
    CoverageTopic("Puerto Rico & LATAM", "organizational psychology Puerto Rico", priority=1),
    CoverageTopic("Puerto Rico & LATAM", "workplace Puerto Rico employees organizational", priority=1),
    CoverageTopic("Puerto Rico & LATAM", "psicología industrial organizacional Puerto Rico", priority=1),
    CoverageTopic("Puerto Rico & LATAM", "desarrollo organizacional Puerto Rico"),
    CoverageTopic("Puerto Rico & LATAM", "liderazgo empleados Puerto Rico"),
    CoverageTopic("Puerto Rico & LATAM", "psicología organizacional América Latina"),
    CoverageTopic("Puerto Rico & LATAM", "recursos humanos América Latina"),
)


def coverage_domains() -> list[str]:
    return list(dict.fromkeys(topic.domain for topic in COVERAGE_TOPICS))


def coverage_queries() -> list[str]:
    return list(dict.fromkeys(topic.query for topic in COVERAGE_TOPICS))


def topics_for_domain(domain: str) -> list[CoverageTopic]:
    return [topic for topic in COVERAGE_TOPICS if topic.domain == domain]


def priority_topics(max_priority: int = 1) -> list[CoverageTopic]:
    return [topic for topic in COVERAGE_TOPICS if topic.priority <= max_priority]

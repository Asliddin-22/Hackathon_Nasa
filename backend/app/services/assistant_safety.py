"""Conservative demo escalation checks, executed before any model call.
This is not comprehensive medical triage; absence of a match does not imply safety.
"""
import re
from .safety import safety_actions
PATTERNS=[r'chest (?:pain|pressure)',r'(?:difficulty|trouble) breathing',r'shortness of breath',r'can(?:not|\x27t) breathe',r'\bfainted\b',r'\bfainting\b',r'passed out',r'loss of consciousness',r'slurred speech',r'(?:one.sided|sudden) weakness',r'sudden (?:vision loss|loss of vision)',r'\bconfusion\b',r'(?:cannot|can\x27t|not) urinat(?:e|ing)']
WARNING='If chest pain, breathing difficulty, fainting, sudden vision loss, or new speech/weakness symptoms occur, contact the onboard crew medical officer immediately and follow actual emergency procedures.'
def check(question,severity=None,warning_signs=False):
    matches=[]
    clauses=re.split(r'[.;,\n]|\bbut\b',question.lower())
    for clause in clauses:
        for pattern in PATTERNS:
            match=re.search(pattern,clause)
            if match:
                before=clause[max(0,match.start()-30):match.start()]
                if re.search(r'\b(no|without|deny|denies|not experiencing)\b',before):continue
                matches.append(match.group())
    urgent=warning_signs or (severity is not None and severity>=8) or bool(matches)
    return {'urgent':urgent,'matched_warning_signs':list(dict.fromkeys(matches)),
            'actions':safety_actions(urgent),'warning':WARNING,
            'scope':'Conservative prototype checks; not validated or comprehensive triage.'}

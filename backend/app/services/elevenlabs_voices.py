from typing import Dict, List

# Registre únic de veus d'ElevenLabs (nom -> voice_id)
ELEVEN_VOICES: Dict[str, str] = {
    "Rachel":   "JBFqnCBsd6RMkjVDRZzb",
    "enguillem":"GU58mv1oQani2qjXfdf8",
    "Dipemo":   "j7XQZUnVCfhpa94EsaJS",
    "grandpa":  "NOpBlnGInO9m6vDvFkFC",
    "reverend": "87tjwokZlpNU7QL3HaLP",
    "benjamin": "80lPKtzJMPh1vjYMUgwe",
    "chuck":    "HpwvRGB4etieKEmtZLPD",
    "camila":   "spPXlKT5a4JMfbhPRAzA",
    "juan":     "koz1BlPszSyECRwl4ZjV",
    "naida":    "6wMKsI8ig8FZUfpyZDIY",
    "nina":     "yqTu7PvIL2rV3ubtjNlx",
    "tatiana":  "2rigMbVWLdqtBSCahJFX",
    "faraon":   "Rl2JPHsuEWSfwCD4ZHIQ",
    "papanoel": "1wg2wOjdEWKA7yQD8Kca",
    "david":    "BNgbHR0DNeZixGQVzloada",
    "antonio":  "9iaRiYAiGlZImkI1Ruyh",
    "sheila":   "dHdIIFZMLzs6XfsGtmIP",
    "beatriz":  "gJlzF5JxsCvM5hQAoRyD",
    "tristan":  "sx7WD8TJIOrk5RQOptDH",
    "davidmartin": "Nh2zY9kknu6z4pZy6FhD"
}

def list_eleven_voices() -> List[str]:
    return sorted(ELEVEN_VOICES.keys())

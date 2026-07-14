"""Transcript fixtures for the 12 mandated voice E2E scenarios.

Each fixture is a list of ASR-annotated audio chunks (what a real ASR would
emit): text, confidence, language, uncertain_terms, barge_in flags.
"""

S1_NORMAL_HVAC_QUOTE = [
    {"text": "Hi, I'd like a quote for a heat pump installation.",
     "confidence": 0.95, "language": "en"},
    {"text": "My name is Jan Kowalski, the house is at ul. Kwiatowa 12 in Poznań.",
     "confidence": 0.93, "language": "en"},
    {"text": "Thursday would work best for me.",
     "confidence": 0.94, "language": "en"},
]

S2_CLIENT_INTERRUPTS = [
    {"text": "I need a quote for air conditioning.",
     "confidence": 0.95, "language": "en"},
    {"text": "Sorry, before you continue - it's actually for two rooms.",
     "confidence": 0.9, "language": "en", "barge_in": True},
]

S3_WRONG_DATA_CORRECTED = [
    {"text": "I want a heat pump quote. My name is Adam Nowak.",
     "confidence": 0.95, "language": "en"},
    {"text": "The address is ul. Polna 5.",
     "confidence": 0.92, "language": "en"},
    {"text": "No, wait, sorry - the address is ul. Lipowa 8, the other one is my office.",
     "confidence": 0.92, "language": "en"},
]

S4_PROMISES_PHOTOS = [
    {"text": "I'd like a quote for replacing my boiler.",
     "confidence": 0.95, "language": "en"},
    {"text": "I'll send you the photos tomorrow, of the boiler and the nameplate.",
     "confidence": 0.9, "language": "en"},
]

S5_REFUSES_ADDRESS = [
    {"text": "How much would a heat pump cost? I need a quote.",
     "confidence": 0.95, "language": "en"},
    {"text": "I don't want to give my address yet, just a rough price please.",
     "confidence": 0.93, "language": "en"},
]

S6_ASKS_FOR_HUMAN = [
    {"text": "I want a quote for AC installation.",
     "confidence": 0.95, "language": "en"},
    {"text": "Actually, I'd prefer to talk to a human about this.",
     "confidence": 0.94, "language": "en"},
]

S7_ANGRY_CLIENT = [
    {"text": "Your technician was supposed to come yesterday and nobody showed up. This is outrageous!",
     "confidence": 0.9, "language": "en"},
]

S8_MIXED_LANGUAGES = [
    {"text": "Dzień dobry, potrzebuję wyceny pompy ciepła.",
     "confidence": 0.92, "language": "pl"},
    {"text": "Das Haus ist, przepraszam, dom jest w Słubicach, blisko granicy.",
     "confidence": 0.75, "language": "de",
     "uncertain_terms": ["Słubicach"]},
]

S9_OUT_OF_SCOPE = [
    {"text": "Hi, do you also do car repair? My engine is making noises.",
     "confidence": 0.95, "language": "en"},
]

S10_RETURNING_CLIENT = [
    {"text": "Hi, you installed my AC last year - I'm calling about the previous order.",
     "confidence": 0.94, "language": "en"},
    {"text": "I'd like a quote for a second unit, same address as last time.",
     "confidence": 0.94, "language": "en"},
]

S11_UNCERTAIN_BRAND = [
    {"text": "I need a boiler service quote.",
     "confidence": 0.95, "language": "en"},
    {"text": "I think it's a Vissmann or something like that, hard to read.",
     "confidence": 0.6, "language": "en",
     "uncertain_terms": ["Vissmann"]},
]

S12_PRICE_WITHOUT_DATA = [
    {"text": "What's the price for a heat pump? Just tell me how much it will cost.",
     "confidence": 0.95, "language": "en"},
]

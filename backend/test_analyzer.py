
from app.ai.complaint_analyzer import analyze_complaint


complaints = [
    "My Refrigerator R-200 makes a loud noise during operation and sometimes stops.",

    "There is a strange smell coming from the Microwave M-50.",

    "The Water Heater WH-30 is not cooling/heating properly anymore.",

    "The Air Conditioner AC-1000 vibrates a lot and shakes the whole room.",

    "The Microwave M-50 stopped working completely after two months.",

    "Water is leaking from the Microwave M-50."
]


for number, complaint in enumerate(complaints, start=1):

    result = analyze_complaint(complaint)

    print("\n" + "=" * 70)
    print(f"COMPLAINT {number}")
    print("=" * 70)

    print("Original:")
    print(complaint)

    print("\nAI/NLP Analysis:")
    print("----------------")

    print(f"Processed Text : {result['processed_text']}")
    print(f"Sentiment      : {result['sentiment']}")
    print(f"Severity       : {result['severity']}")
    print(f"Symptoms       : {result['symptoms']}")
    print(f"Category       : {result['category']}")
    print(f"Model Version  : {result['model_version']}")

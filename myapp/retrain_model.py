import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# Features used by the model
FEATURES = [
    "fever", "headache", "nausea", "vomiting", "fatigue",
    "joint_pain", "skin_rash", "cough", "weight_loss", "yellow_eyes"
]

# Diseases mapped in views.py
DISEASES = [
    "aids", "acne", "alcoholic hepatitis", "allergy", "arthritis",
    "bronchial asthma", "cervical spondylosis", "chronic cholestasis",
    "dengue", "diabetes", "dimorphic hemorrhoids(piles)", "drug reaction",
    "gerd", "gastroenteritis", "heart attack", "hepatitis a", "hepatitis b",
    "hepatitis c", "hepatitis d", "hepatitis e", "hypertension",
    "hyperthyroidism", "hypoglycemia", "hypothyroidism", "impetigo",
    "jaundice", "malaria", "migraine", "osteoarthritis",
    "paralysis (brain hemorrhage)", "peptic ulcer disease", "pneumonia",
    "psoriasis", "tuberculosis", "typhoid", "urinary tract infection",
    "varicose veins", "vertigo (benign paroxysmal positional vertigo)"
]

def main():
    # Create a dummy dataset
    # We will generate a few samples for each disease with random features
    np.random.seed(42)
    n_samples_per_class = 10
    
    X_data = []
    y_data = []
    
    for disease in DISEASES:
        for _ in range(n_samples_per_class):
            # Random binary features
            X_data.append(np.random.randint(0, 2, size=len(FEATURES)))
            y_data.append(disease)
            
    df = pd.DataFrame(X_data, columns=FEATURES)
    y = np.array(y_data)
    
    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    # Train a fast model
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(df, y_encoded)
    
    # Save the model
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "best_model.pkl")
    le_path = os.path.join(base_dir, "label_encoder.pkl")
    
    joblib.dump(model, model_path)
    joblib.dump(le, le_path)
    
    print(f"Successfully retrained and saved model to {model_path}")

if __name__ == "__main__":
    main()

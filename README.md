# Weather Prediction Model

A machine learning web application that predicts weather conditions from uploaded CSV data, built with **Streamlit** and **XGBoost Classifier**.

The primary focus of the model is predicting whether the weather condition will be Rain or Sun based on meteorological features.

🔗 Live Demo: https://myweatherpredictionmodel.streamlit.app/



#  Model Performance

| Metric                 | Score  |
| ---------------------- | ------ |
| Accuracy               | 0.8519 |
| Macro Avg Precision    | 0.7083 |
| Macro Avg Recall       | 0.5687 |
| Macro Avg F1-Score     | 0.6151 |
| Weighted Avg Precision | 0.8331 |
| Weighted Avg Recall    | 0.8519 |
| Weighted Avg F1-Score  | 0.8380 |

## Classification Report

| Weather Condition | Precision | Recall | F1-Score | Support |
| ----------------- | --------- | ------ | -------- | ------- |
| Drizzle           | 0.5714    | 0.3333 | 0.4211   | 12      |
| Fog               | 0.2143    | 0.1154 | 0.1500   | 26      |
| Rain              | 0.9239    | 0.9529 | 0.9381   | 191     |
| Snow              | 1.0000    | 0.5385 | 0.7000   | 13      |
| Sun               | 0.8318    | 0.9036 | 0.8662   | 197     |

> The model achieves strong performance in predicting Rain and Sun weather conditions, which are the primary focus of the application. The Rain class achieves a Precision of 0.9239, Recall of 0.9529, and F1-Score of 0.9381, while the Sun class achieves a Precision of 0.8318, Recall of 0.9036, and F1-Score of 0.8662. The model uses meteorological features to provide accurate weather condition predictions.


## Model Details

* Algorithm: XGBoost Classifier (`XGBClassifier`)

* Preprocessing: Feature transformation pipeline

* Input Features:

  * Precipitation
  * Maximum Temperature
  * Minimum Temperature
  * Wind Speed

* Output: Predicted weather condition

### 1. Clone the repository


git clone https://github.com/thePython2016/weatherPredictionModel.git
cd weatherPredictionModel


### 2. Install dependencies


pip install -r requirements.txt


### 3. Run the app


streamlit run app.py

## Sample Data

Use the provided `sample_data.csv` to test the app format.


# World of Games and Data 🎮

## URL

The URL for the website is [https://laihoangson.github.io/world-of-games-and-data-2/](https://laihoangson.github.io/world-of-games-and-data-2/)

## PC Games Collection

### 🐍 Neon Snake
Classic snake game with modern neon aesthetics, power-ups, and dynamic obstacles.

### ✈️ Flappy Plane Adventure
Side-scrolling flight game with shooting mechanics, coin collection, and UFO enemies.

### 🎹 Interactive Piano & Cat Game
Dual application featuring a functional web piano and an endless runner cat game.

### 🧱 Neon Brick Breaker
Arcade brick breaker with power-ups, multiple levels, and neon visual effects.

See the videos to learn how to play the PC games here: https://drive.google.com/drive/folders/1MoglukpwKfDFlNKquAvJ0Esi65AaFzk0?usp=sharing

## 📊 Advanced Analytics System & Interactive Dashboard

The *Flappy Plane Adventure* game is integrated with a live, real-time analytics system. It actively tracks player performance metrics, game session durations, score distributions, and detailed death reasons.

### 🚀 Live Analytics Server

The backend analytics API and PostgreSQL database are fully deployed and hosted live on the cloud. You do not need to run any local servers to view the data.

* **Live Dashboard:** Available directly on the website under the "Analysis" tab.
* **Backend API Endpoint:** `https://flappy-analytics.onrender.com`
* **Database:** PostgreSQL (Hosted on Render)

*Simply play a few rounds of Flappy Plane on the website, and your gameplay data will be instantly synced and visualized on the Live Analytics Dashboard!*

## Data Analysis Report "Game Analytics: From Exploratory Data Analysis to Predictive Modeling"

### 🔍 Key Analysis Features:

**📈 Exploratory Data Analysis (EDA)**
- Score and gameplay duration distributions
- Death reason analysis and patterns  
- Correlation between game metrics
- Player performance visualization
- Behavioral feature engineering (aggressiveness, efficiency, risk-taking, etc)

**🤖 Machine Learning & Predictive Modeling**
- **Data Bootstrapping**: Augmented 250 samples to 10,000+ training dataset
- **Holdout Validation**: 50-sample test set for unbiased model evaluation
- **Score Regression**: Random Forest model with near-perfect accuracy (R² = 0.996) for final score prediction
- **Survival Prediction**: Binary classification to forecast player survival beyond 30-second expert threshold (98% accuracy)
- **Death Reason Classification**: Multiclass XGBoost model predicting specific causes of player failure
- **Player Segmentation**: K-means clustering identifying 3 distinct behavioral profiles (Novices, Average Players, Experts)

**🎯 Business Intelligence**
- Actionable recommendations for player retention and monetization
- Game balancing insights based on player behavior patterns
- Targeted engagement strategies for different player segments
- Data-driven game design improvements


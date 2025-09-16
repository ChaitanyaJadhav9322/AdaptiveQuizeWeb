## How to Set Up and Deploy Your Quiz App 🚀

This guide provides a step-by-step process for setting up your quiz application locally and deploying it to Render.

-----

### 1\. Folder Structure 📁

Your project should follow a clean, organized structure to ensure all components are in the right place.

```
quiz_app/
├── app.py
├── requirements.txt
├── runtime.txt
├── .env
├── .gitignore
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── script.js
```

  * **`app.py`**: The main Python application file.
  * **`requirements.txt`**: Lists all the Python dependencies.
  * **`runtime.txt`**: Specifies the Python version for deployment (e.g., `python-3.12.0`).
  * **`.env`**: Stores local environment variables (not uploaded to Git).
  * **`.gitignore`**: Tells Git which files and folders to ignore.
  * **`templates/`**: Contains HTML templates.
  * **`static/`**: Holds static assets like CSS and JavaScript.

-----

### 2\. Installations and Dependencies 💻

Before you can run the app, you need to install the required libraries.

1.  **Install Python**: Ensure you have a recent version of Python (3.12 or later) installed.
2.  **Create a virtual environment**: This keeps your project dependencies isolated.
    ```bash
    python -m venv venv
    ```
3.  **Activate the environment**:
      * **On Windows**: `venv\Scripts\activate`
      * **On macOS/Linux**: `source venv/bin/activate`
4.  **Install dependencies**: Install all the libraries listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

-----

### 3\. Database and Environment Setup 💾

Your app requires a PostgreSQL database and environment variables for sensitive information.

1.  **PostgreSQL**: Install PostgreSQL locally or use a cloud service like Render to create a new database.
2.  **`.env` file**: Create a `.env` file in your project's root and add your database and API keys. **This file should not be pushed to Git**.
    ```
    GEMINI_API_KEY="your_gemini_api_key"
    POSTGRES_DB_NAME="your_db_name"
    POSTGRES_DB_USER="your_db_user"
    POSTGRES_DB_PASSWORD="your_db_password"
    POSTGRES_DB_HOST="your_db_host"
    POSTGRES_DB_PORT="your_db_port"
    ```

-----

### 4\. Git and GitHub 🔗

Use Git to manage your project's version history and push it to GitHub for deployment.

1.  **Initialize Git**: Turn your project folder into a Git repository.
    ```bash
    git init
    ```
2.  **Add and Commit**: Stage and commit all your files.
    ```bash
    git add .
    git commit -m "Initial commit of the project"
    ```
3.  **Connect to GitHub**: Link your local repository to a new, empty repository on GitHub.
    ```bash
    git remote add origin https://github.com/ChaitanyaJadhav9322/AdaptiveQuizeWeb.git
    ```
4.  **Push to GitHub**: Upload your files to the remote repository.
    ```bash
    git push -u origin main
    ```

-----

### 5\. Deployment to Render ☁️

1.  **Create a new Web Service**: Log in to Render, click **"New"**, and select **"Web Service"**.
2.  **Connect your GitHub repository**.
3.  **Configure Environment Variables**: In the **"Environment"** section, add all the variables from your local `.env` file. You can also use the single **Internal Database URL** provided by Render.
4.  **Set Build and Start Commands**:
      * **Build Command**: `pip install -r requirements.txt`
      * **Start Command**: `gunicorn app:app`
5.  **Deploy**: Click **"Create Web Service"**. Render will automatically build and deploy your application.

Your live website is now accessible at: [https://adaptivequizeweb.onrender.com/](https://adaptivequizeweb.onrender.com/) 


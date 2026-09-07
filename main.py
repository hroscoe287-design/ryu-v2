from flask import Flask

app = Flask(__name__)

DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>Ryu V2</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            background: #0b1020;
            color: white;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 30px;
        }
        .box {
            max-width: 900px;
            margin: auto;
            background: #151c30;
            padding: 30px;
            border-radius: 16px;
        }
        h1 {
            margin-top: 0;
        }
        .status {
            color: #35d07f;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="box">
        <h1>RYU V2</h1>
        <p class="status">● ONLINE</p>
        <p>Ryu V2 trading dashboard is running.</p>
    </div>
</body>
</html>
"""

@app.route("/")
def home():
    return DASHBOARD

@app.route("/health")
def health():
    return "OK", 200

from flask import Flask, render_template_string, jsonify
import os
import random
from datetime import datetime

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ryu V2</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #071b12;
    color: #ffffff;
    font-family: Arial, sans-serif;
}

.header {
    padding: 18px;
    background: linear-gradient(135deg, #09281a, #0d4a2a);
    border-bottom: 1px solid #1c7042;
}

.logo {
    font-size: 28px;
    font-weight: 900;
    color: #43ff91;
}

.subtitle {
    color: #9ccdb1;
    font-size: 13px;
    margin-top: 4px;
}

.nav {
    display: flex;
    gap: 8px;
    padding: 12px;
    overflow-x: auto;
    background: #06150e;
}

.nav button {
    background: #103522;
    color: #b9e8c9;
    border: 1px solid #245f3e;
    padding: 10px 16px;
    border-radius: 8px;
}

.nav button.active {
    background: #18a957;
    color: white;
}

.container {
    padding: 14px;
    max-width: 1100px;
    margin: auto;
}

.filters {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 14px;
}

select {
    width: 100%;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #276e48;
    background: #0b291a;
    color: white;
}

.card {
    background: #0a2517;
    border: 1px solid #1b5e39;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 14px;
}

.signal-card {
    text-align: center;
    padding: 22px;
}

.signal {
    font-size: 42px;
    font-weight: 900;
    margin: 12px 0;
}

.call {
    color: #35ff83;
}

.put {
    color: #ff5964;
}

.wait {
    color: #ffd45a;
}

.confidence {
    font-size: 20px;
    color: #b8e8c9;
}

.stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
}

.stat {
    background: #0d321f;
    border-radius: 10px;
    padding: 12px;
}

.stat-title {
    font-size: 11px;
    color: #8fb9a0;
}

.stat-value {
    font-size: 19px;
    font-weight: bold;
    margin-top: 5px;
}

.chart {
    height: 270px;
    position: relative;
    overflow: hidden;
    background:
        linear-gradient(rgba(50,255,130,.07) 1px, transparent 1px),
        linear-gradient(90deg, rgba(50,255,130,.07) 1px, transparent 1px);
    background-size: 40px 40px;
    border: 1px solid #1d7545;
    border-radius: 10px;
}

.chart svg {
    width: 100%;
    height: 100%;
}

.fireball {
    text-align: center;
    font-size: 70px;
    margin: 5px 0;
    filter: drop-shadow(0 0 12px #ff7b00);
}

.confluence {
    display: flex

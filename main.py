from flask import Flask, jsonify, render_template_string
import random
import math
import time
from datetime import datetime

app = Flask(__name__)

# ============================================================
# RYU V2 — FULL VISUAL DASHBOARD
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>RYU V2 — AI Trading Dashboard</title>

<style>
*{
    box-sizing:border-box;
    margin:0;
    padding:0;
}

html,body{
    width:100%;
    min-height:100%;
    font-family:Arial,Helvetica,sans-serif;
    background:#020b07;
    color:#fff;
}

body{
    overflow-x:hidden;
}

/* ================= BACKGROUND ================= */

body:before{
    content:"";
    position:fixed;
    inset:0;
    background:
        linear-gradient(rgba(0,255,110,.035) 1px,transparent 1px),
        linear-gradient(90deg,rgba(0,255,110,.035) 1px,transparent 1px);
    background-size:35px 35px;
    pointer-events:none;
    z-index:0;
}

.glow{
    position:fixed;
    width:500px;
    height:500px;
    border-radius:50%;
    background:rgba(0,255,100,.08);
    filter:blur(90px);
    left:-180px;
    top:100px;
    z-index:0;
}

.glow2{
    position:fixed;
    width:450px;
    height:450px;
    border-radius:50%;
    background:rgba(0,180,255,.05);
    filter:blur(100px);
    right:-180px;
    bottom:-100px;
    z-index:0;
}

/* ================= HEADER ================= */

header{
    position:relative;
    z-index:5;
    height:76px;
    border-bottom:1px solid rgba(0,255,120,.2);
    background:rgba(2,12,8,.92);
    backdrop-filter:blur(12px);
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 22px;
}

.logo{
    display:flex;
    align-items:center;
    gap:12px;
}

.logo-mark{
    width:47px;
    height:47px;
    border:2px solid #00ff72;
    border-radius:12px;
    display:flex;
    align-items:center;
    justify-content:center;
    color:#00ff72;
    font-weight:900;
    font-size:21px;
    box-shadow:0 0 22px rgba(0,255,100,.3);
}

.logo-text{
    font-size:24px;
    font-weight:900;
    letter-spacing:2px;
}

.logo-text span{
    color:#00ff72;
}

.status{
    display:flex;
    align-items:center;
    gap:8px;
    font-size:12px;
    color:#72ffab;
}

.status-dot{
    width:9px;
    height:9px;
    background:#00ff72;
    border-radius:50%;
    box-shadow:0 0 12px #00ff72;
    animation:pulse 1.3s infinite;
}

@keyframes pulse{
    50%{opacity:.35;transform:scale(.7);}
}

/* ================= NAV ================= */

nav{
    position:relative;
    z-index:4;
    display:flex;
    gap:4px;
    padding:10px 20px;
    border-bottom:1px solid rgba(0,255,120,.12);
    background:rgba(1,8,5,.85);
    overflow-x:auto;
}

nav button{
    border:0;
    background:transparent;
    color:#789184;
    padding:11px 18px;
    border-radius:8px;
    cursor:pointer;
    font-weight:bold;
    white-space:nowrap;
}

nav button.active,
nav button:hover{
    color:#00ff72;
    background:rgba(0,255,100,.08);
}

/* ================= MAIN ================= */

.main{
    position:relative;
    z-index:2;
    max-width:1500px;
    margin:auto;
    padding:18px;
}

.top-grid{
    display:grid;
    grid-template-columns:250px 1fr 310px;
    gap:16px;
}

.panel{
    border:1px solid rgba(0,255,110,.18);
    background:rgba(3,18,11,.78);
    border-radius:14px;
    box-shadow:0 8px 35px rgba(0,0,0,.35);
    overflow:hidden;
}

.panel-title{
    padding:14px 16px;
    border-bottom:1px solid rgba(0,255,100,.12);
    font-size:12px;
    color:#7d998b;
    letter-spacing:1.3px;
    text-transform:uppercase;
}

/* ================= RYU ================= */

.ryu-panel{
    min-height:570px;
    position:relative;
    background:
        radial-gradient(circle at 50% 65%,rgba(0,255,90,.14),transparent 35%),
        linear-gradient(180deg,rgba(3,18,11,.9),rgba(1,8,5,.98));
}

.ryu-title{
    position:absolute;
    top:18px;
    left:18px;
    font-size:22px;
    font-weight:900;
    letter-spacing:2px;
    color:#fff;
    z-index:2;
}

.ryu-title span{
    color:#00ff72;
}

.ryu-stage{
    position:absolute;
    left:0;
    right:0;
    top:65px;
    bottom:0;
    overflow:hidden;
}

/* stylized Ryu */

.ryu{
    position:absolute;
    left:50%;
    top:53%;
    width:120px;
    height:240px;
    transform:translate(-50%,-50%);
}

.head{
    position:absolute;
    width:52px;
    height:55px;
    background:#d69a69;
    border-radius:48% 48% 43% 43%;
    left:34px;
    top:7px;
    z-index:4;
}

.hair{
    position:absolute;
    width:72px;
    height:65px;
    left:23px;
    top:-5px;
    z-index:5;
}

.hair:before,
.hair:after{
    content:"";
    position:absolute;
    background:#161616;
    width:32px;
    height:48px;
    transform:skew(-18deg) rotate(15deg);
    top:0;
}

.hair:before{
    left:4px;
}

.hair:after{
    right:3px;
    transform:skew(18deg) rotate(-15deg);
}

.bandana{
    position:absolute;
    z-index:6;
    width:61px;
    height:11px;
    background:#dfe6df;
    top:36px;
    left:29px;
    transform:rotate(-3deg);
}

.body{
    position:absolute;
    top:57px;
    left:29px;
    width:64px;
    height:105px;
    background:#ddd;
    border-radius:18px 18px 10px 10px;
    z-index:2;
}

.belt{
    position:absolute;
    top:137px;
    left:24px;
    width:75px;
    height:

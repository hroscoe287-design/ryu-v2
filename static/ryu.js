"use strict";

/*
 * Ryu V2 Dashboard Controller
 * Front-end only.
 * The backend can later replace demo data with a verified live feed.
 */

const RYU = {
    selectedAsset: "EUR/USD OTC",
    selectedCategory: "FOREX",
    selectedTimeframe: "5m",
    expiryMinutes: 5,
    signal: "WAIT",
    confidence: 0,
    entryPrice: 0,
    currentPrice: 0,
    countdown: 0,
    candles: [],
    history: [],
    demoMode: true
};

const ASSETS = {
    FOREX: [
        "EUR/USD OTC",
        "GBP/USD OTC",
        "USD/JPY OTC",
        "AUD/USD OTC",
        "EUR/GBP OTC",
        "USD/CHF OTC",
        "USD/CAD OTC",
        "EUR/JPY OTC",
        "GBP/JPY OTC",
        "AUD/JPY OTC"
    ],

    CRYPTO: [
        "BTC/USD OTC",
        "ETH/USD OTC",
        "SOL/USD OTC",
        "XRP/USD OTC"
    ],

    STOCKS: [
        "Apple",
        "Tesla",
        "Microsoft",
        "NVIDIA",
        "Amazon"
    ],

    COMMODITIES: [
        "Gold",
        "Silver",
        "Natural Gas",
        "Oil"
    ],

    INDICES: [
        "US 30",
        "US 500",
        "US Tech 100",
        "GER 40",
        "UK 100"
    ]
};

const TIMEFRAMES = [
    "1m",
    "2m",
    "3m",
    "5m",
    "10m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "12h",
    "1D",
    "1W",
    "1M"
];

document.addEventListener("DOMContentLoaded", () => {
    initializeRyu();
});

function initializeRyu() {
    createDemoCandles();
    bindNavigation();
    bindCategories();
    bindTimeframes();
    bindAssets();
    startClock();
    startMarketSimulation();
    renderEverything();
}

/* ---------------------------------------------------------
   NAV

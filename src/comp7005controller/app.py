"""
Basic flask application.
"""

import os
from argparse import ArgumentParser
from flask import Flask, request, redirect, render_template, make_response
from flask import request, jsonify

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def home_page():
    """Home page of the flask app."""
    return render_template("index.html")


sc_drop = 0
cs_drop = 0
window_size = 1


@app.route("/config", methods=["POST"])
def apply_config():
    global sc_drop, cs_drop, window_size
    content = request.json
    cs_drop = content["client_server_drop"]
    sc_drop = content["server_client_drop"]
    window_size = content["window_size"]

    return ""


@app.route("/config", methods=["GET"])
def get_config():
    global sc_drop, cs_drop, window_size

    return {
        "client_server_drop": cs_drop,
        "server_client_drop": sc_drop,
        "window_size": window_size,
    }


statistics = {
    "client_sent": 0,
    "client_recv": 0,
    "proxy_sent": 0,
    "proxy_recv": 0,
    "server_sent": 0,
    "server_recv": 0
}


@app.route("/statistics", methods=["POST"])
def share_delta():
    content = request.json

    for k in statistics.keys():
        if k in content:
            statistics[k] += content[k]

    return ""


@app.route("/statistics", methods=["DELETE"])
def reset_stats():
    for k in statistics.keys():
        statistics[k] = 0

    return ""


@app.route("/statistics", methods=["GET"])
def load_stats():
    return {
        "sample": statistics
    }


def controller_main():
    parser = ArgumentParser(
        prog='controller',
        description='GUI for monitoring and manipulating network properties for file-transfer stream protocol.')

    parser.add_argument(
        "--port",
        type=int,
        default=5000
    )

    args = parser.parse_args()

    app.run(port=args.port)


if __name__ == "__main__":
    controller_main()

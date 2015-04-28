from flask import jsonify


def not_found():
    return jsonify({'error': 'Not found', 'status': 404}), 404


def server_error():
    return jsonify({'error': 'Server error', 'status': 500}), 500

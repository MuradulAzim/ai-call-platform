#!/bin/bash
curl -s http://localhost:8200/chat -X POST \
  -H 'Content-Type: application/json' \
  -d '{"message":"hey bro","user":"Azim","relationship":"self"}'
echo ""

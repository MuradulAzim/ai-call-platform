#!/bin/sh
curl -s -X POST http://localhost:8000/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@iamazim.com","password":"Admin123!"}'
echo

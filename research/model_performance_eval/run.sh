# locust -f evaluate.py --headless --users 100 --spawn-rate 10 --run-time 5m > stress_test_output_qwen3_30b.txt
locust -f evaluate.py --headless -u 1 -r 1 --host=http://10.0.0.16:11434

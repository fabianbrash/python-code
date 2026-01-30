import torch
import time

# Check GPU
# we need to run pip install torch first to run the script

assert torch.cuda.is_available(), "CUDA GPU not available"

device = torch.device("cuda")

# Create large random tensors
size = 8192
a = torch.randn(size, size, device=device)
b = torch.randn(size, size, device=device)

print("Starting GPU workload...")

start = time.time()
for i in range(200):
    c = torch.matmul(a, b)  # heavy GPU operation
    c = torch.relu(c)
    if i % 20 == 0:
        torch.cuda.synchronize()
        print(f"Iteration {i}")

torch.cuda.synchronize()
print(f"Done in {time.time() - start:.2f} seconds")

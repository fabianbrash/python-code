import os
import time

import torch
import torch.nn as nn

# ---- Device (forced to CPU) -----------------------------------------------
device = "cpu"
print(f"torch {torch.__version__} | device: {device} | threads: {torch.get_num_threads()}")

# ---- Synthetic data (identical to the GPU script) -------------------------
torch.manual_seed(0)
N, D, C = 100_000, 128, 10
X = torch.randn(N, D)
y = (X @ torch.randn(D, C)).argmax(dim=1)
split = int(N * 0.8)
X_train, y_train = X[:split], y[:split]
X_val, y_val = X[split:], y[split:]
BATCH = 2048
n_batches = (split + BATCH - 1) // BATCH


# ---- Model (identical to the GPU script) ----------------------------------
def make_model():
    return nn.Sequential(
        nn.Linear(D, 1024), nn.ReLU(),
        nn.Linear(1024, 1024), nn.ReLU(),
        nn.Linear(1024, C),
    )


model = make_model()
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
loss_fn = nn.CrossEntropyLoss()


def accuracy(m, Xv, yv):
    m.eval()
    correct = 0
    with torch.no_grad():
        for xb, yb in zip(Xv.split(2048), yv.split(2048)):
            correct += (m(xb).argmax(dim=1) == yb).sum().item()
    return correct / yv.numel()


# ---- Train (fp32; no mixed precision on CPU) ------------------------------
EPOCHS = 20
start = time.time()
for epoch in range(1, EPOCHS + 1):
    model.train()
    running = 0.0
    for idx in torch.randperm(split).split(BATCH):
        xb, yb = X_train[idx], y_train[idx]
        opt.zero_grad(set_to_none=True)
        loss = loss_fn(model(xb), yb)
        loss.backward()
        opt.step()
        running += loss.item()
    print(f"epoch {epoch:2d}/{EPOCHS} | loss {running / n_batches:.4f} "
          f"| val acc {accuracy(model, X_val, y_val):.4f}")
print(f"training time: {time.time() - start:.1f}s")

# ---- Save -----------------------------------------------------------------
save_dir = os.path.expanduser("~/models")
os.makedirs(save_dir, exist_ok=True)
path = os.path.join(save_dir, "mlp_synthetic_cpu.pt")
torch.save(model.state_dict(), path)
print(f"saved model to {path} ({os.path.getsize(path) / 1e6:.1f} MB)")

# ---- Reload check ---------------------------------------------------------
restored = make_model()
restored.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
print(f"reloaded model val acc: {accuracy(restored, X_val, y_val):.4f}")

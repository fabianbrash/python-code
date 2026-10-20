import os
import time

import torch
import torch.nn as nn

# ---- Device ---------------------------------------------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
use_amp = device == "cuda"  # fp16 mixed precision (Turing GPUs have no bf16)
print(f"torch {torch.__version__} | device: {device}", end="")
print(f" | {torch.cuda.get_device_name(0)}" if use_amp else "")

# ---- Synthetic data, kept on the GPU (no DataLoader, no CPU batching) -----
torch.manual_seed(0)
N, D, C = 100_000, 128, 10
X = torch.randn(N, D)
y = (X @ torch.randn(D, C)).argmax(dim=1)
split = int(N * 0.8)
X_train, y_train = X[:split].to(device), y[:split].to(device)
X_val, y_val = X[split:].to(device), y[split:].to(device)
BATCH = 2048
n_batches = (split + BATCH - 1) // BATCH


# ---- Model ----------------------------------------------------------------
def make_model():
    return nn.Sequential(
        nn.Linear(D, 1024), nn.ReLU(),
        nn.Linear(1024, 1024), nn.ReLU(),
        nn.Linear(1024, C),
    )


model = make_model().to(device)
opt = torch.optim.Adam(model.parameters(), lr=1e-3, fused=use_amp)
loss_fn = nn.CrossEntropyLoss()
scaler = torch.amp.GradScaler("cuda", enabled=use_amp)


def accuracy(m, Xv, yv):
    m.eval()
    dev = next(m.parameters()).device
    correct = 0
    with torch.no_grad():
        for xb, yb in zip(Xv.split(2048), yv.split(2048)):
            xb, yb = xb.to(dev), yb.to(dev)
            correct += (m(xb).argmax(dim=1) == yb).sum().item()
    return correct / yv.numel()


# ---- Train ----------------------------------------------------------------
EPOCHS = 20
start = time.time()
for epoch in range(1, EPOCHS + 1):
    model.train()
    running = torch.zeros((), device=device)
    for idx in torch.randperm(split, device=device).split(BATCH):
        xb, yb = X_train[idx], y_train[idx]
        opt.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
            loss = loss_fn(model(xb), yb)
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
        running += loss.detach()
    print(f"epoch {epoch:2d}/{EPOCHS} | loss {running.item() / n_batches:.4f} "
          f"| val acc {accuracy(model, X_val, y_val):.4f}")
if use_amp:
    torch.cuda.synchronize()
print(f"training time: {time.time() - start:.1f}s")

# ---- Save -----------------------------------------------------------------
save_dir = os.path.expanduser("~/models")
os.makedirs(save_dir, exist_ok=True)
path = os.path.join(save_dir, "mlp_synthetic.pt")
torch.save(model.state_dict(), path)
print(f"saved model to {path} ({os.path.getsize(path) / 1e6:.1f} MB)")

# ---- Reload check (loads onto CPU to prove the file is self-contained) ----
restored = make_model()
restored.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
print(f"reloaded model val acc (CPU): {accuracy(restored, X_val.cpu(), y_val.cpu()):.4f}")

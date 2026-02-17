import pyxdf
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

def marker_label(name, timestamp):
    return f"{name} ({timestamp:.2f}s)"

xdf_path = r"C:\Users\andik\Documents\CurrentStudy\sub-P001\ses-S001\eeg\sub-P001_ses-S001_task-Default_run-001_eeg.xdf"
streams, fileheader = pyxdf.load_xdf(xdf_path, synchronize_clocks=True)

eeg = None
for s in streams:
    if s["info"]["type"][0].lower() == "eeg":
        eeg = s
        break

raw_eeg = np.array(eeg["time_series"]).astype(float).flatten()
ts_abs_eeg = np.array(eeg["time_stamps"])
fs = float(eeg["info"]["nominal_srate"][0])
t = ts_abs_eeg - ts_abs_eeg[0]

markers = None
for s in streams:
    if s["info"]["type"][0].lower() == "markers":
        markers = s
        break

if markers is None:
    marker_times = []
    marker_values = []
else:
    marker_abs = np.array(markers["time_stamps"])
    marker_times = marker_abs - marker_abs[0]
    marker_values = [m[0] for m in markers["time_series"]]

cut_samples = int(2.5 * fs)
if len(raw_eeg) > cut_samples:
    raw_eeg = raw_eeg[:-cut_samples]
    t = t[:-cut_samples]
else:
    raise RuntimeError

dataset = raw_eeg

notch_freq = 50
numerator, denominator = signal.iirnotch(notch_freq, 20, fs)
filtered_notch_data = signal.filtfilt(b=numerator, a=denominator, x=dataset, padtype=None)

denom, nom = signal.iirfilter(3, [0.1, 4], btype="bandpass", ftype="butter", fs=fs, output="ba")
filtered_bp_data = signal.filtfilt(b=denom, a=nom, x=filtered_notch_data, padtype=None)



"""plt.figure(figsize=(15, 5))
plt.plot(t, dataset)
for mt, mv in zip(marker_times, marker_values):
    plt.axvline(mt, color="red", alpha=0.5)
    plt.text(mt, np.max(dataset)*0.9, marker_label(mv, mt),
             rotation=90, fontsize=7, color="red")
plt.title("Raw EEG + Markers")
plt.xlabel("Time [s]")
plt.ylabel("Raw")
plt.tight_layout()
plt.show()"""

plt.figure(figsize=(15, 5))
plt.plot(t, filtered_bp_data)
for mt, mv in zip(marker_times, marker_values):
    plt.axvline(mt, color="tab:red", alpha=0.5)
    plt.text(mt, np.max(filtered_bp_data)*0.9, marker_label(mv, mt),
             rotation=90, fontsize=7, color="tab:red")
plt.title("EEG Signal")
plt.xlabel("Time [s]")
plt.ylabel("Amplitude")
plt.tight_layout()
plt.show()


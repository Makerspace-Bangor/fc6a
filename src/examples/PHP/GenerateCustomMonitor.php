<?php
// =============================================================
// PHP: Generate Python Logger for Multiple FC6A PLCs
// - Logs every configured data point to one daily CSV file
// - CSV filename: logs_YYYY-MM-DD.csv
// - Two-line header:
//     row 1: PLC/source names
//     row 2: register names
// - Optional live matplotlib visuals per checked register
// - 4-hour display window at 1 Hz by default
// =============================================================

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $plcs = [];
    $p = 1;

    while (isset($_POST["ip_$p"])) {
        $name = substr(preg_replace("/[^A-Za-z0-9_]/", "", $_POST["name_$p"]), 0, 20);
        $ip = $_POST["ip_$p"];
        $endian = isset($_POST["endian_$p"]) ? "1" : "0";

        if (!filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
            die("Invalid IP address for PLC #$p");
        }

        $regs = [];
        if (isset($_POST["reg_name_$p"])) {
            for ($i = 0; $i < count($_POST["reg_name_$p"]); $i++) {
                $r_name = preg_replace("/[^A-Za-z0-9_]/", "", $_POST["reg_name_$p"][$i]);
                $r_addr = strtoupper($_POST["reg_addr_$p"][$i]);
                $r_type = strtoupper($_POST["reg_type_$p"][$i]);
                $r_visual = isset($_POST["reg_visual_{$p}_{$i}"]) ? "True" : "False";

                if ($r_name && preg_match("/^[DM][0-9]{4}$/", $r_addr) && in_array($r_type, ["B", "F", "W"])) {
                    $regs[] = "            (\"$r_name\", \"$r_addr\", \"$r_type\", $r_visual),";
                }
            }
        }

        if (!empty($regs)) {
            $plcs[] = [
                'name' => $name,
                'ip' => $ip,
                'endian' => $endian,
                'registers' => implode("\n", $regs)
            ];
        }

        $p++;
    }

    if (empty($plcs)) {
        die("No valid PLCs or registers provided.");
    }

    // --- Build Python ---
    $plc_blocks = [];
    foreach ($plcs as $cfg) {
        $plc_blocks[] = <<<PY
    {
        "name": "{$cfg['name']}",
        "ip": "{$cfg['ip']}",
        "device": "FF",
        "endian": "{$cfg['endian']}",
        "registers": [
{$cfg['registers']}
        ],
    }
PY;
    }

    $plc_str = implode(",\n", $plc_blocks);

    $py = <<<PY
#!/usr/bin/env python3
import csv, time, os, datetime, itertools
from collections import defaultdict, deque

try:
    from fc6a import FC6AMaint
except ImportError:
    print("fc6a module not found, downloading from GitHub...")
    import requests
    url = "https://raw.githubusercontent.com/Makerspace-Bangor/fc6a/main/src/fc6a.py"
    code = requests.get(url, timeout=20).text
    exec(code, globals())
    print("fc6a module loaded from GitHub.")

PLC_CONFIGS = [
$plc_str
]

SAMPLE_INTERVAL_SECONDS = 1
DISPLAY_HISTORY_POINTS = 4 * 60 * 60  # 4 hours at 1 Hz
LOG_DIR = "."

COLOR_LIST = ["red", "green", "blue", "purple", "orange", "pink"]

def get_csv_filename():
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"logs_{date_str}.csv")

def build_combined_headers(active_plcs):
    source_header = ["timestamp"]
    register_header = ["timestamp"]

    for cfg in active_plcs:
        for tag, _reg, _dtype, _visual in cfg["registers"]:
            source_header.append(cfg["name"])
            register_header.append(tag)

    return source_header, register_header

def ensure_csv_header(filename, source_header, register_header):
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(source_header)
            writer.writerow(register_header)

def read_plc_values(cfg):
    plc = FC6AMaint(cfg["ip"])
    swapped = bool(int(cfg.get("endian", "0")))
    data = {}

    for tag, reg, dtype, _visual in cfg["registers"]:
        try:
            rnum = int(reg[1:])

            if dtype == "F":
                val = round(plc.read_float(rnum, swapped), 2)
            elif dtype == "W":
                val = plc.read_word(rnum)
            elif dtype == "B":
                val = plc.read_bits(rnum)
            else:
                val = None

        except Exception as e:
            print(f"Error reading {tag} from {cfg['name']} at {cfg['ip']}: {e}")
            val = None

        data[tag] = val

    return data

def log_all_plcs(active_plcs):
    now = datetime.datetime.now()
    timestamp = now.isoformat(timespec="seconds")
    readings = {}

    source_header, register_header = build_combined_headers(active_plcs)
    filename = get_csv_filename()

    ensure_csv_header(filename, source_header, register_header)

    row = [timestamp]

    for cfg in active_plcs:
        row_values = read_plc_values(cfg)

        readings[cfg["ip"]] = {
            "name": cfg["name"],
            "timestamp": now,
            "values": row_values
        }

        for tag, _reg, _dtype, _visual in cfg["registers"]:
            row.append(row_values.get(tag, ""))

    with open(filename, "a", newline="") as f:
        csv.writer(f).writerow(row)

    return readings

def selected_visual_items(active_plcs):
    items = []

    for cfg in active_plcs:
        for tag, _reg, dtype, visual in cfg["registers"]:
            if visual and dtype in ("F", "W", "B"):
                items.append((cfg["ip"], cfg["name"], tag))

    return items

def update_visuals(fig, axes, lines, history, visual_items, mdates):
    for ax, (plc_ip, plc_name, tag) in zip(axes, visual_items):
        points = list(history[(plc_ip, tag)])
        line = lines[(plc_ip, tag)]

        if points:
            x_vals = [mdates.date2num(p[0]) for p in points]
            y_vals = [p[1] for p in points]

            line.set_data(x_vals, y_vals)
            ax.relim()
            ax.autoscale_view()

    if axes:
        axes[-1].set_xlabel("Time")

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.canvas.draw_idle()

def main():
    # Limit to 5 PLCs max
    active_plcs = PLC_CONFIGS[:5]

    plc_colors = {
        cfg["ip"]: color
        for cfg, color in zip(active_plcs, itertools.cycle(COLOR_LIST))
    }

    visual_items = selected_visual_items(active_plcs)
    history = defaultdict(lambda: deque(maxlen=DISPLAY_HISTORY_POINTS))

    plt = None
    fig = None
    axes = []
    lines = {}

    if visual_items:
        import matplotlib.pyplot as plt_module
        import matplotlib.dates as mdates

        plt = plt_module

        fig, axes_obj = plt.subplots(
            len(visual_items),
            1,
            figsize=(11, max(3, len(visual_items) * 2.4)),
            sharex=True
        )

        axes = axes_obj.flatten().tolist() if hasattr(axes_obj, "flatten") else [axes_obj]

        for ax, (plc_ip, plc_name, tag) in zip(axes, visual_items):
            line, = ax.plot(
                [],
                [],
                label=f"{plc_name}:{tag}",
                color=plc_colors.get(plc_ip)
            )

            lines[(plc_ip, tag)] = line

            ax.set_ylabel(tag)
            ax.grid(True)
            ax.legend(loc="upper right")

            ax.xaxis_date()
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))

        axes[-1].set_xlabel("Time")

        fig.suptitle("FC6A Live Trends - Last 4 Hours at 1 Hz")

        plt.ion()
        plt.show(block=False)

    print(f"Logging {len(active_plcs)} PLC(s) every {SAMPLE_INTERVAL_SECONDS} second(s) into: {os.path.abspath(LOG_DIR)}")
    print("CSV file pattern: logs_YYYY-MM-DD.csv")

    if visual_items:
        print("Visualizing checked numeric registers:")
        for plc_ip, plc_name, tag in visual_items:
            print(f"  {plc_name} ({plc_ip}):{tag}")
    else:
        print("No numeric registers checked for visualization. Logging only.")

    while True:
        readings = log_all_plcs(active_plcs)

        if visual_items:
            for plc_ip, plc_name, tag in visual_items:
                reading = readings.get(plc_ip)

                if not reading:
                    continue

                val = reading["values"].get(tag)
                if isinstance(val, (int, float)):
                    history[(plc_ip, tag)].append((reading["timestamp"], val))
                else:
                    # Add a gap when connection is lost
                    history[(plc_ip, tag)].append((reading["timestamp"], float("nan")))
            update_visuals(fig, axes, lines, history, visual_items, mdates)
            plt.pause(0.05)

        time.sleep(SAMPLE_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\\nExiting gracefully.")
PY;

    $filename = "FC6A_" . date("Ymd_His") . ".py";

    header("Content-Type: application/octet-stream");
    header("Content-Disposition: attachment; filename=\"$filename\"");
    echo $py;
    exit;
}
?>

<!DOCTYPE html>
<html>
<head>
<title>Generate FC6A Python Logger</title>
<link rel="stylesheet" href="css/layo.css" type="text/css">
<link rel="shortcut icon" href="http://www.hackmaine.org/favicon.ico">

<script>
let plcCount = 1;
let regCounts = {1: 1};

function registerRowHtml(plcIndex, regIndex, checked) {
    const checkedText = checked ? " checked" : "";

    return `
        <div>
            Name: <input name="reg_name_${plcIndex}[]" required>
            Addr: <input name="reg_addr_${plcIndex}[]" pattern="^[DMdm][0-9]{4}$" required placeholder="D0002">
            Type:
            <select name="reg_type_${plcIndex}[]">
                <option value="F">F</option>
                <option value="B">B</option>
                <option value="W">W</option>
            </select>
            Visual: <input type="checkbox" name="reg_visual_${plcIndex}_${regIndex}"${checkedText}>
        </div><br>`;
}

function addRegisterRow(plcIndex) {
    const regContainer = document.getElementById(`registers_${plcIndex}`);
    const regIndex = regCounts[plcIndex] || 0;

    regContainer.insertAdjacentHTML("beforeend", registerRowHtml(plcIndex, regIndex, false));
    regCounts[plcIndex] = regIndex + 1;
}

function addPLC() {
    plcCount++;
    regCounts[plcCount] = 1;

    const plcContainer = document.getElementById("plc_container");

    plcContainer.insertAdjacentHTML("beforeend", `
        <fieldset id="plc_${plcCount}">
            <legend>PLC #${plcCount}</legend>

            <label>Name (20 chars max):</label><br>
            <input type="text" name="name_${plcCount}" maxlength="20" required><br><br>

            <label>IP Address:</label><br>
            <input type="text" name="ip_${plcCount}" required placeholder="10.10.10.58"><br><br>

            <label>Endian:</label>
            <input type="checkbox" name="endian_${plcCount}"> (checked = 1, unchecked = 0)<br><br>

            <h3>Registers</h3>
            <div id="registers_${plcCount}">
                ${registerRowHtml(plcCount, 0, true)}
            </div>

            <button type="button" onclick="addRegisterRow(${plcCount})">Add Register Row</button>
        </fieldset>
    `);
}
</script>
</head>

<body>
<h2>Generate Custom FC6A Logger Script</h2>

Logs daily CSV files to the directory where the script is run.<br>
Live 4-hour window sampled at 1 Hz.<br>
Check the Visual box to add registers to plot.<br>
The class library downloads from the official repo, via a network connection.<br>
You could still download and install the fc6a library from:<br>

<a href="https://github.com/Makerspace-Bangor/fc6a/blob/main/src/fc6a.py">
https://github.com/Makerspace-Bangor/fc6a/blob/main/src/fc6a.py
</a><br>

<br>
<b>How to use this page:</b>
<a href="https://github.com/Makerspace-Bangor/fc6a/blob/main/documentation/doc.pdf">
See repo documentation.
</a>

<br><br>

<form method="post">
<div id="plc_container">
    <fieldset id="plc_1">
        <legend>PLC #1</legend>

        <label>Name (20 chars max):</label><br>
        <input type="text" name="name_1" maxlength="20" required><br><br>

        <label>IP Address:</label><br>
        <input type="text" name="ip_1" required placeholder="10.10.10.57"><br><br>

        <label>Endian:</label>
        <input type="checkbox" name="endian_1"> (checked = 1, unchecked = 0)<br><br>

        <h3>Registers</h3>
        <div id="registers_1">
            <div>
                Name: <input name="reg_name_1[]" required>
                Addr: <input name="reg_addr_1[]" pattern="^[DMdm][0-9]{4}$" required placeholder="D0002">
                Type:
                <select name="reg_type_1[]">
                    <option value="F">F</option>
                    <option value="B">B</option>
                    <option value="W">W</option>
                </select>
                Visual: <input type="checkbox" name="reg_visual_1_0" checked>
            </div><br>
        </div>

        <button type="button" onclick="addRegisterRow(1)">Add Register Row</button>
    </fieldset>
</div>

<br>
<button type="button" onclick="addPLC()">Add Another PLC</button>
<br><br>

<input type="submit" value="Generate Python File">
</form>

<br>
</body>
</html>

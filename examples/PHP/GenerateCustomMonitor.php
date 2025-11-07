<?php
// =============================================================
// PHP: Generate Python Logger for Multiple FC6A PLCs
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

                if ($r_name && preg_match("/^[DM][0-9]{4}$/", $r_addr) && in_array($r_type, ["B","F","W"])) {
                    $regs[] = "            (\"$r_name\", \"$r_addr\", \"$r_type\"),";
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
import matplotlib.pyplot as plt
try:
    from fc6a import FC6AMaint
except ImportError:
    print("fc6a module not found, downloading from GitHub...")
    import requests
    url = "https://raw.githubusercontent.com/Makerspace-Bangor/fc6a/main/src/fc6a.py"
    code = requests.get(url).text
    exec(code, globals())  # inject FC6AMaint
    print("fc6a module loaded from GitHub.")

PLC_CONFIGS = [
$plc_str
]

def get_csv_filename(cfg):
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    return f"{cfg['name']}_{{date_str}}.csv"

def ensure_csv_header(filename, fieldnames):
    if not os.path.exists(filename):
        with open(filename, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()

def read_plc_values(cfg):
    plc = FC6AMaint(cfg["ip"])
    swapped = bool(int(cfg.get("endian", "0")))
    data = {}
    for tag, reg, dtype in cfg["registers"]:
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
            print(f"Error reading {tag} from {cfg['name']}: {e}")
            val = None
        data[tag] = val
    return data

def main():
    # Limit to 5 PLCs max
    active_plcs = PLC_CONFIGS[:5]
    colors = itertools.cycle(["red", "green", "purple", "orange", "pink"])

    # Collect all unique tag names
    unique_tags = sorted(set(tag for cfg in active_plcs for tag, _, _ in cfg["registers"]))
    n = len(unique_tags)
    fig, axes = plt.subplots(n, 1, figsize=(10, n * 2.5), sharex=True)
    if n == 1:
        axes = [axes]

    fig.suptitle("Multi-PLC Live Trends (1 Hz)")
    plt.ion()

    timestamps = []
    values = {tag: {cfg["name"]: [] for cfg in active_plcs} for tag in unique_tags}
    plc_colors = {cfg["name"]: next(colors) for cfg in active_plcs}

    while True:
        now = datetime.datetime.now()
        timestamps.append(now)
        timestamps = timestamps[-3600:]

        # read each PLC and update stored values
        for cfg in active_plcs:
            row = read_plc_values(cfg)
            for tag, val in row.items():
                if tag not in values:
                    continue
                values[tag][cfg["name"]].append(val)
                # keep history length equal to timestamps
                if len(values[tag][cfg["name"]]) > len(timestamps):
                    values[tag][cfg["name"]] = values[tag][cfg["name"]][-len(timestamps):]

        # redraw all tag subplots
        for i, tag in enumerate(unique_tags):
            ax = axes[i]
            ax.clear()
            for cfg in active_plcs:
                series = values[tag][cfg["name"]]
                # only plot if we have at least one valid data point
                if not series:
                    continue
                # align list lengths safely
                y = series[-len(timestamps):]
                x = timestamps[-len(y):]
                color = plc_colors[cfg["name"]]
                ax.plot(x, y, label=cfg["name"], color=color)
            ax.set_ylabel(tag)
            ax.legend(loc="upper right")
            ax.grid(True)

        axes[-1].set_xlabel("Time")
        plt.tight_layout()
        plt.pause(0.1)
        time.sleep(1)

        
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
<style>
fieldset { border: 1px solid #888; margin-bottom: 1em; padding: 1em; }
legend { font-weight: bold; }
button { margin-top: 0.5em; }
</style>
<script>
let plcCount = 1;

function addRegisterRow(plcIndex) {
    const regContainer = document.getElementById(`registers_${plcIndex}`);
    regContainer.insertAdjacentHTML("beforeend", `
        <div>
            Name: <input name="reg_name_${plcIndex}[]" required>
            Addr: <input name="reg_addr_${plcIndex}[]" pattern="^[DMdm][0-9]{4}$" required placeholder="D0002">
            Type:
            <select name="reg_type_${plcIndex}[]">
                <option value="F">F</option>
                <option value="B">B</option>
                <option value="W">W</option>
            </select>
        </div><br>`);
}

function addPLC() {
    plcCount++;
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
                <div>
                    Name: <input name="reg_name_${plcCount}[]" required>
                    Addr: <input name="reg_addr_${plcCount}[]" pattern="^[DMdm][0-9]{4}$" required placeholder="D0002">
                    Type:
                    <select name="reg_type_${plcCount}[]">
                        <option value="F">F</option>
                        <option value="B">B</option>
                        <option value="W">W</option>
                    </select>
                </div><br>
            </div>
            <button type="button" onclick="addRegisterRow(${plcCount})">Add Register Row</button>
        </fieldset>
    `);
}
</script>
</head>

<body>
<h2>Generate Custom FC6A Monitor Script</h2>
<br>You will need network connectivity to your PLC for this<br>
script generator to work, so we have included the ability to get<br>
the class library from the official repo, via a network connection.<br>
-- you could still download and installl the fc6a library from:<br>
<a href="https://github.com/Makerspace-Bangor/fc6a/blob/main/src/fc6a.py">https://github.com/Makerspace-Bangor/fc6a/blob/main/src/fc6a.py</a><br> 
The generated script requires Python3.<br><br>
<br><b>How to use this page:</b>
<br> See repo documentation.
<br>





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
            </div><br>
        </div>
        <button type="button" onclick="addRegisterRow(1)">Add Register Row</button>
    </fieldset>
</div>

<button type="button" onclick="addPLC()">Add Another PLC</button>
<br><br>
<input type="submit" value="Generate Python File">
</form>
<br> Your browser may warn you about this file type <br>
<br>
<br>
<br>
</body>
</html>


















<?php
// WIP: only generates PLC_CONFIGS
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $name = substr(preg_replace("/[^A-Za-z0-9_]/", "", $_POST['name']), 0, 20);
    $ip = $_POST['ip'];
    $endian = isset($_POST['endian']) ? "1" : "0";

    // Validate IPv4
    if (!filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
        die("Invalid IP address");
    }

    // Process registers
    $registers = [];
    if (isset($_POST['reg_name'])) {
        for ($i = 0; $i < count($_POST['reg_name']); $i++) {

            $r_name = preg_replace("/[^A-Za-z0-9_]/", "", $_POST['reg_name'][$i]);
            $r_addr = strtoupper($_POST['reg_addr'][$i]);
            $r_type = strtoupper($_POST['reg_type'][$i]);

            if ($r_name && preg_match("/^[DM][0-9]{4}$/", $r_addr) && in_array($r_type, ["B","F","W"])) {
                $registers[] = "            (\"$r_name\", \"$r_addr\", \"$r_type\"),";
            }
        }
    }

    if (empty($registers)) {
        die("No valid registers provided.");
    }

    // Build Python program
    $py = "#!/usr/bin/env python3

PLC_CONFIGS = [
    {
        \"name\": \"$name\",
        \"ip\": \"$ip\",
        \"device\": \"FF\",
        \"endian\": \"$endian\",
        \"registers\": [
" . implode("\n", $registers) . "
        ],
    },
]



    // Filename with date+time
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
<title>Generate Custom PLC Monitor</title>
<script>
function addRow() {
    const container = document.getElementById("registers");
    container.insertAdjacentHTML("beforeend", `
        <div>
            Name: <input name="reg_name[]" required>
            Addr: <input name="reg_addr[]" pattern="^[DMdm][0-9]{4}$" required placeholder="D0002 or M0000">
            Type:
            <select name="reg_type[]">
                <option value="B">B</option>
                <option value="F">F</option>
                <option value="W">W</option>
            </select>
        </div><br>`);
}
</script>
</head>
<body>
<h2>Generate Custom PLC Monitor</h2>
<form method="post">
<label>Name (20 chars max):</label><br>
<input type="text" name="name" maxlength="20" required><br><br>
<label>IP Address:</label><br>
<input type="text" name="ip" required placeholder="10.10.10.57"><br><br>
<label>Endian:</label>
<input type="checkbox" name="endian"> (checked = 1, unchecked = 0)
<br><br>
<h3>Registers</h3>
<div id="registers">
  <div>
  Name: <input name="reg_name[]" required>
  Addr: <input name="reg_addr[]" pattern="^[DMdm][0-9]{4}$" required placeholder="D0002">
  Type:
  <select name="reg_type[]">
  <option value="B">B</option>
  <option value="F">F</option>
  <option value="W">W</option>
  </select>
  </div><br>
</div>
<button type="button" onclick="addRow()">Add Register</button>
<br><br>
<input type="submit" value="Generate Custom PLC Monitor">
</form>
</body>
</html>


# Currency Canvas

## Run locally

```text
python server.py
```

Open <http://localhost:8000>. The app persists favorites and conversion history in
`currency_converter.db`. Set `EXCHANGERATE_HOST_ACCESS_KEY` before starting the server
to authenticate live conversion rates and the exchangerate.host timeseries request
used by the 30-day chart. The key is read from the environment and is never stored in
the project.

Set the variable in the same PowerShell window used to start the server:

```powershell
$env:EXCHANGERATE_HOST_ACCESS_KEY = "your-key"
python server.py
```

If the server was already running, restart it after setting the variable. The browser
cannot configure this backend secret.

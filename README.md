# Currency Canvas

## Run locally

```text
python server.py
```

Open <http://localhost:8000>. The app persists favorites and conversion history in
`currency_converter.db`. Set `EXCHANGERATE_HOST_ACCESS_KEY` before starting the server
to authenticate the exchangerate.host timeseries request used by the 30-day chart.
`EXCHANGERATE_API_KEY` can also be set for live latest-rate responses.

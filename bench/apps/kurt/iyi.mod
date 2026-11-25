# Dependencies. `iyi get -u` moves them to their latest releases.
module kurt

require github.com/iyikurt/kurt v0.1.0 as kurt
require github.com/sdogruyol/iyi-web v0.7.0 as web
require github.com/iyilang/db v0.6.0 as db
require github.com/iyilang/sqlite v0.6.0 as sqlite

# Kurt from a checkout on this machine (KURT_PATH).
replace github.com/iyikurt/kurt => /Users/alperen/Projects/tulpar

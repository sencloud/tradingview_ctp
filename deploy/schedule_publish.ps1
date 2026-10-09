<#
  把「重算策略 → 上传看板」这条管线挂到 Windows 计划任务，替代"想起来才手动跑"。

  为什么必须自动化：喜宽 App 的策略页读的就是这份 dashboard.json，而策略唯一
  可执行的输出是调仓指令。数据一旦停更，App 里展示的就是过期指令——按旧名单下单
  是真金白银的风险。App 侧只能做到"标黄提示"，根子还是要让管线按时跑。

  用法：
    powershell -File deploy\schedule_publish.ps1 -Install     # 装（工作日 15:35）
    powershell -File deploy\schedule_publish.ps1 -Status      # 看任务 + 数据新鲜度
    powershell -File deploy\schedule_publish.ps1 -RunNow      # 立刻跑一次
    powershell -File deploy\schedule_publish.ps1 -Remove      # 卸载
#>
[CmdletBinding()]
param(
  [switch]$Install,
  [switch]$Remove,
  [switch]$Status,
  [switch]$RunNow,
  [switch]$SkipFetch,
  [string]$Time = '15:35',
  [string]$TaskName = 'SingzQuant-Publish'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot          # 仓库根目录
$logDir = Join-Path $PSScriptRoot 'logs'
$logFile = Join-Path $logDir 'publish.log'
$publish = Join-Path $PSScriptRoot 'publish.py'
$strat = Join-Path $root 'stk_strategies'

if (-not (Test-Path $publish)) { throw "找不到 $publish" }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Invoke-Publish {
  # 三步缺一不可：publish.py 只是"用本地缓存重算"，不取数——只跑它会拿到
  # 一份信号日期还停在上次的旧结果。必须先刷新日线行情与因子表。
  $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  "[$stamp] publish 开始" | Out-File -FilePath $logFile -Append -Encoding utf8

  $code = 0
  if (-not $SkipFetch) {
    foreach ($step in @(
        @{ name = 's_fetch 日线行情'; file = 's_fetch.py'; args = @('--universe', 'union') },
        @{ name = 'f_fetch 因子表'; file = 'f_fetch.py'; args = @('--universe', 'sse50', '--tables', 'all') }
      )) {
      "[$stamp] $($step.name) 开始" | Out-File -FilePath $logFile -Append -Encoding utf8
      $out = & python (Join-Path $strat $step.file) @($step.args) 2>&1
      $code = $LASTEXITCODE
      $out | Out-File -FilePath $logFile -Append -Encoding utf8
      "[$stamp] $($step.name) 结束 exit=$code" | Out-File -FilePath $logFile -Append -Encoding utf8
      # 取数失败就不要继续：用旧数据重算出来的信号日期是旧的，发上去会误导人。
      if ($code -ne 0) { break }
    }
  }
  if ($code -eq 0) {
    $out = & python $publish 2>&1
    $code = $LASTEXITCODE
    $out | Out-File -FilePath $logFile -Append -Encoding utf8
  }
  "[$stamp] publish 结束 exit=$code" | Out-File -FilePath $logFile -Append -Encoding utf8
  return $code
}

if ($Install) {
  # 只在当前用户登录时运行：策略数据源在本机（tushare 授权 + 行情缓存），
  # 机器没开机时跑不了，硬报错反而更糟——App 侧会用"数据截至"提示兜住。
  # 用 ScheduledTasks 模块而不是 schtasks.exe：路径里的引号交给模块处理，
  # 手写 /TR 的转义在含空格路径上很容易翻车。
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -RunNow" `
    -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $Time
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Force `
    -Description '喜宽主策略数据：收盘后重算并上传看板（App 策略页读的就是它）' |
    Out-Null
  Write-Host "已安装计划任务 $TaskName：工作日 $Time 自动重算并上传"
  Write-Host "日志：$logFile"
  exit 0
}

if ($Remove) {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "已卸载计划任务 $TaskName"
  } else {
    Write-Host "没有找到计划任务 $TaskName（可能本来就没装）"
  }
  exit 0
}

if ($RunNow) {
  exit (Invoke-Publish)
}

# 默认 = Status
Write-Host "== 计划任务 =="
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
  Write-Host "未安装（用 -Install 安装）"
} else {
  $info = Get-ScheduledTaskInfo -TaskName $TaskName
  Write-Host "任务 $TaskName：$($task.State)"
  Write-Host "上次运行 $($info.LastRunTime) ｜ 结果码 $($info.LastTaskResult)"
  Write-Host "下次运行 $($info.NextRunTime)"
}

Write-Host ""
Write-Host "== 数据新鲜度 =="
$dash = Join-Path $PSScriptRoot 'app\data\dashboard.json'
if (-not (Test-Path $dash)) {
  Write-Host "还没有 dashboard.json，先跑一次 publish"
  exit 0
}
$d = Get-Content $dash -Raw -Encoding utf8 | ConvertFrom-Json
$gen = $d.generated_at
$until = $d.params.until
$today = Get-Date -Format 'yyyy-MM-dd'
Write-Host "生成时间 $gen ｜ 数据截至 $until ｜ 今天 $today"

if ($until -eq $today) {
  Write-Host "OK：数据是最新的"
} else {
  # 优先用本机已缓存的交易所日历算"落后几个交易日"——数工作日会把国庆/春节
  # 整段算进去，7 个工作日其实只有 2 个交易日，差得太远。
  $calCsv = Join-Path $root 'stk_strategies\factor_data\_market\trade_cal.csv'
  $days = $null
  if (Test-Path $calCsv) {
    $cal = Import-Csv $calCsv
    $u = $until.Replace('-', ''); $t = $today.Replace('-', '')
    $maxCal = ($cal | Measure-Object -Property cal_date -Maximum).Maximum
    if ($maxCal -ge $t) {
      $days = @($cal | Where-Object {
        $_.is_open -eq '1' -and $_.cal_date -gt $u -and $_.cal_date -le $t
      }).Count
    }
  }
  if ($null -eq $days) {
    Write-Host "（本机交易日历不可用，退回按工作日估算）"
    $a = [datetime]::Parse($until); $b = [datetime]::Parse($today); $days = 0
    for ($x = $a.AddDays(1); $x -le $b; $x = $x.AddDays(1)) {
      if ($x.DayOfWeek -ne 'Saturday' -and $x.DayOfWeek -ne 'Sunday') { $days++ }
    }
  }
  if ($days -gt 0) {
    Write-Host "警告：数据落后 $days 个交易日，请跑 -RunNow 补一次"
  } else {
    Write-Host "OK：最新交易日的数据已在（今天不是交易日）"
  }
}

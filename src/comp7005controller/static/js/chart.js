
function create_chart() {
    chart = new Highcharts.Chart('graph-container', {
        navigator: {
          enabled: true
        },
        title: {
            text: 'Data-Flow Statistics'
        },
        yAxis: {
            title: {
                text: '# Packets Transmitted'
            },
            min: 0,
        },
        xAxis: {
            type: "datetime",
            title: {text: "Datetime"},
            labels: {
                rotation: -60,
                align: "right",
                format: '{value:%M:%S}',
            },
            tickPixelInterval: 50,
            tickmarkPlacement: "on",
            id: 'x-axis',
        },
        legend: {
            layout: 'vertical',
            align: 'right',
            verticalAlign: 'middle'
        },
        plotOptions: {
            series: {
                showInNavigator: true,
                showCheckbox: true
            }
        },
        series: [
            {
                selected: true,
                showInNavigator: true,
                data: [],
                name: "Client (Send)",
                type: undefined
            },
            {
                selected: true,
                showInNavigator: true,
                data: [],
                name: "Client (Recv)",
                type: undefined
            },
            {
                selected: false,
                showInNavigator: true,
                data: [],
                name: "Proxy (Send)",
                type: undefined
            },
            {
                selected: false,
                showInNavigator: true,
                data: [],
                name: "Proxy (Recv)",
                type: undefined
            },
            {
                selected: true,
                showInNavigator: true,
                data: [],
                name: "Server (Send)",
                type: undefined
            },
            {
                selected: true,
                showInNavigator: true,
                data: [],
                name: "Server (Recv)",
                type: undefined
            }
        ],
    });

    Highcharts.each(chart.legend.allItems, function (p, i) {
      $(p.checkbox).change(
        function () {
          if (this.checked) {
            chart.legend.allItems[i].show();
          } else {
            chart.legend.allItems[i].hide();
          }
        });
    });

    return chart
}

function send_config() {
    $.ajax({
        type: "POST",
        url: "/config",
        // The key needs to match your method's input parameter (case-sensitive).
        data: JSON.stringify({
            client_server_drop: parseInt(document.getElementById("cliServDrop").value),
            server_client_drop: parseInt(document.getElementById("servCliDrop").value),
            window_size: parseInt(document.getElementById("windowSize").value)
        }),
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        error: function(errMsg) {
            console.error(errMsg)
        }
    });
}

function reset_stats() {
    $.ajax({
        type: "DELETE",
        url: "/statistics"
    });
}

function reset_view() {
    chart.series.forEach((x) => x.setData([]))
}


function refresh_data() {
    //console.log($("cliServDrop"))
    //console.log($("servCliDrop"))
    //console.log($("windowSize").value)

    $.ajax({
        url: "/statistics",
        dataType: 'json',
        success: function(raw) {
            time = Date.now()
            chart.series[0].addPoint([time, raw.sample.client_sent])
            chart.series[1].addPoint([time, raw.sample.client_recv])
            chart.series[2].addPoint([time, raw.sample.proxy_sent])
            chart.series[3].addPoint([time, raw.sample.proxy_recv])
            chart.series[4].addPoint([time, raw.sample.server_sent])
            chart.series[5].addPoint([time, raw.sample.server_recv])
            //date = Date.now()
            //data_.push([date, temp])
            //console.log(data_)
            //plot_chart()
        }
    })
}

$(document).ready(function() {

    var chart = create_chart();
    refresh_data()
    setInterval(function() { refresh_data() }, 1000);
});

const months = [
    { name: "January", days: 31 },
    { name: "February", days: 29 },
    { name: "March", days: 31 },
    { name: "April", days: 30 },
    { name: "May", days: 31 },
    { name: "June", days: 30 },
    { name: "July", days: 31 },
    { name: "August", days: 31 },
    { name: "September", days: 30 },
    { name: "October", days: 31 },
    { name: "November", days: 30 },
    { name: "December", days: 31 }
];


document.addEventListener("DOMContentLoaded", function(){
    let monthSelect = document.createElement("select");
    monthSelect.id = 'month';
    
    for (var i = 0; i < months.length; i++) {
        var monthOption = document.createElement("option");
        monthOption.value = i + 1;
        monthOption.text = months[i].name;
        monthSelect.appendChild(monthOption);
    }
    
    let daySelect = document.createElement("select");
    daySelect.id = 'day';
    
    function updateDaySelector(monthNum, dayNum) {
        daySelect.innerHTML = '';
        
        for (var i = 1; i <= months[parseInt(monthNum)].days; i++) {
            var dayOption = document.createElement("option");
            dayOption.value = i;
            dayOption.text = i;
            daySelect.appendChild(dayOption);
        }

        monthSelect.value = monthNum;
        daySelect.value = dayNum || 1;
    }

    monthSelect.addEventListener("change", (_) => {
        updateDaySelector(monthSelect.value);
    });
    
    var button = document.createElement('button');
    button.innerText = 'Go';
    button.addEventListener('click', (_) => {
        document.location.href = '/on-this-day/' + monthSelect.value + '/' + daySelect.value;
    });

    var container = document.getElementById('on-this-day-select');
    container.appendChild(monthSelect);
    container.appendChild(daySelect);
    container.appendChild(button);

    updateDaySelector(
        document.getElementById('current-month').value,
        document.getElementById('current-day').value
    );
});


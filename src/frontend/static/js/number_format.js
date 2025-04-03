/**
 * Utility functions for formatting numbers with Russian abbreviations
 */

/**
 * Format a number with Russian abbreviations
 * @param {number} number - The number to format
 * @param {number} precision - Number of decimal places for abbreviated numbers (default: 1)
 * @param {boolean} useAbbreviation - Whether to use abbreviations (default: true)
 * @returns {string} Formatted number string
 */
function formatNumberRu(number, precision = 1, useAbbreviation = true) {
    if (number === null || number === undefined || isNaN(number)) {
        return "0";
    }

    // Convert to number if it's a string
    number = Number(number);

    // For small numbers, just format with space separator
    if (!useAbbreviation || Math.abs(number) < 1000) {
        if (Number.isInteger(number)) {
            return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
        } else {
            return number.toFixed(precision).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
        }
    }

    // Russian abbreviations for large numbers
    let value, suffix;

    if (Math.abs(number) >= 1_000_000_000) {
        value = number / 1_000_000_000;
        suffix = "млрд";
    } else if (Math.abs(number) >= 1_000_000) {
        value = number / 1_000_000;
        suffix = "млн";
    } else {  // >= 1000
        value = number / 1_000;
        suffix = "тыс";
    }

    // Format value with specified precision
    if (precision === 0 || Number.isInteger(value)) {
        return `${Math.round(value)} ${suffix}`;
    } else {
        // Round to specified precision
        const roundedValue = Math.round(value * Math.pow(10, precision)) / Math.pow(10, precision);

        // Check if rounding made it an integer
        if (Number.isInteger(roundedValue)) {
            return `${roundedValue} ${suffix}`;
        } else {
            // Replace decimal point with comma for Russian format
            return `${roundedValue.toFixed(precision).replace(".", ",")} ${suffix}`;
        }
    }
}

/**
 * Format a time duration in seconds to a Russian time string
 * @param {number} seconds - Number of seconds
 * @returns {string} Formatted time string
 */
function formatTimeRu(seconds) {
    if (seconds < 60) {
        return `${seconds} сек`;
    }

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
        return `${minutes} мин`;
    }

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (hours < 24) {
        if (remainingMinutes === 0) {
            return `${hours} ч`;
        }
        return `${hours} ч ${remainingMinutes} мин`;
    }

    const days = Math.floor(hours / 24);
    const remainingHours = hours % 24;

    // Russian grammatical rules for days
    let dayStr;
    if (days === 1) {
        dayStr = "день";
    } else if (days > 1 && days < 5) {
        dayStr = "дня";
    } else {
        dayStr = "дней";
    }

    if (remainingHours === 0) {
        return `${days} ${dayStr}`;
    }

    return `${days} ${dayStr} ${remainingHours} ч`;
}

/**
 * Format a timestamp as time with hours and minutes
 * @param {string|Date} timestamp - ISO timestamp string or Date object
 * @returns {string} Formatted time string (HH:MM)
 */
function formatTimeHM(timestamp) {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;

    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    return `${hours}:${minutes}`;
}

/**
 * Format a timestamp in Russian format
 * @param {string|Date} timestamp - ISO timestamp string or Date object
 * @returns {string} Formatted date and time string in Russian
 */
function formatTimestampRu(timestamp) {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;

    // Russian month names in genitive case
    const ruMonths = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ];

    const day = date.getDate();
    const month = ruMonths[date.getMonth()];
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    return `${day} ${month} ${year} в ${hours}:${minutes}`;
}

/**
 * Format a timestamp as a relative time string in Russian
 * @param {string|Date} timestamp - ISO timestamp string or Date object
 * @returns {string} Formatted relative time string in Russian
 */
function formatRelativeTimeRu(timestamp) {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    const now = new Date();
    const diffMs = now - date;

    // Convert to seconds
    const seconds = Math.floor(diffMs / 1000);

    if (seconds < 60) {
        return "только что";
    }

    if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        if (minutes === 1) {
            return "1 минуту назад";
        } else if (minutes > 1 && minutes < 5) {
            return `${minutes} минуты назад`;
        } else {
            return `${minutes} минут назад`;
        }
    }

    if (seconds < 86400) { // 24 hours
        const hours = Math.floor(seconds / 3600);
        if (hours === 1) {
            return "1 час назад";
        } else if (hours > 1 && hours < 5) {
            return `${hours} часа назад`;
        } else {
            return `${hours} часов назад`;
        }
    }

    if (seconds < 604800) { // 7 days
        const days = Math.floor(seconds / 86400);
        if (days === 1) {
            return "вчера";
        } else if (days === 2) {
            return "позавчера";
        } else if (days > 2 && days < 5) {
            return `${days} дня назад`;
        } else {
            return `${days} дней назад`;
        }
    }

    // For older dates, use the formatted date
    return formatTimestampRu(date);
}
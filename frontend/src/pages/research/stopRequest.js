// Cancel the click before React swaps Stop for the submit button.
export function stopRequest(event, controller) {
  event.preventDefault();
  controller?.abort();
}

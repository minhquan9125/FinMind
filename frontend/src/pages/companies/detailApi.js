import { getCompanyFinancials } from "./financials.js";

export const getCompanyDetail = (ticker) => getCompanyFinancials(ticker);
